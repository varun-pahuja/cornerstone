"""Baseline sign classifier: multinomial logistic regression in pure numpy.

Small enough to train in seconds on a Pi, deterministic given `seed`, and
exportable to ONNX as a single affine + softmax graph (no framework runtime
needed at inference — onnxruntime only).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class BaselineNotTrained(Exception):
    pass


class LogisticBaseline:
    """Softmax regression with standardization, L2, full-batch gradient descent."""

    def __init__(self, lr: float = 0.5, epochs: int = 40, l2: float = 1e-3, seed: int = 42):
        self.lr = lr
        self.epochs = epochs
        self.l2 = l2
        self.seed = seed
        self.classes: list[str] = []
        self.W: np.ndarray | None = None  # (D, K)
        self.b: np.ndarray | None = None  # (K,)
        self.mu: np.ndarray | None = None  # (D,) standardization mean
        self.sigma: np.ndarray | None = None  # (D,) standardization std

    # ---- training ----

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        progress_cb=None,
    ) -> list[float]:
        """Train; y holds class-label strings. Returns per-epoch loss history."""
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y)
        if X.ndim != 2 or X.shape[0] != y.shape[0]:
            raise ValueError("X/y shape mismatch")
        self.classes = sorted(set(y.tolist()))
        if len(self.classes) < 2:
            raise ValueError(
                f"need at least 2 classes to train, got {len(self.classes)}: {self.classes}"
            )
        k = len(self.classes)
        d = X.shape[1]
        class_index = {c: i for i, c in enumerate(self.classes)}

        # standardize (stored for inference)
        self.mu = X.mean(axis=0)
        self.sigma = X.std(axis=0)
        self.sigma[self.sigma < 1e-9] = 1.0
        Xs = (X - self.mu) / self.sigma

        y_idx = np.array([class_index[v] for v in y])
        Y = np.zeros((X.shape[0], k))
        Y[np.arange(X.shape[0]), y_idx] = 1.0  # one-hot

        rng = np.random.default_rng(self.seed)
        self.W = rng.normal(0.0, 0.01, size=(d, k))
        self.b = np.zeros(k)

        n = X.shape[0]
        losses: list[float] = []
        for epoch in range(self.epochs):
            logits = Xs @ self.W + self.b
            logits -= logits.max(axis=1, keepdims=True)  # softmax stability
            exp = np.exp(logits)
            probs = exp / exp.sum(axis=1, keepdims=True)
            loss = float(-np.mean(np.log(probs[np.arange(n), y_idx] + 1e-12)))
            loss += 0.5 * self.l2 * float(np.sum(self.W**2))
            losses.append(loss)

            grad_logits = (probs - Y) / n
            grad_W = Xs.T @ grad_logits + self.l2 * self.W
            grad_b = grad_logits.sum(axis=0)
            self.W -= self.lr * grad_W
            self.b -= self.lr * grad_b

            if progress_cb is not None:
                progress_cb(epoch + 1, self.epochs, loss)
        return losses

    # ---- inference ----

    def _check(self) -> None:
        if self.W is None or self.b is None or not self.classes:
            raise BaselineNotTrained("model has not been trained or loaded")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        self._check()
        X = np.asarray(X, dtype=np.float64)
        Xs = (X - self.mu) / self.sigma
        logits = Xs @ self.W + self.b
        logits -= logits.max(axis=1, keepdims=True)
        exp = np.exp(logits)
        return exp / exp.sum(axis=1, keepdims=True)

    def predict(self, X: np.ndarray) -> list[tuple[str, float]]:
        probs = self.predict_proba(X)
        idx = probs.argmax(axis=1)
        return [(self.classes[i], float(probs[r, i])) for r, i in enumerate(idx)]

    # ---- persistence ----

    def save(self, path: str | Path) -> None:
        self._check()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            W=self.W, b=self.b, mu=self.mu, sigma=self.sigma,
            classes=np.array(self.classes, dtype=object),
            meta=np.array(
                json.dumps({"lr": self.lr, "epochs": self.epochs, "l2": self.l2, "seed": self.seed})
            ),
        )

    @classmethod
    def load(cls, path: str | Path) -> "LogisticBaseline":
        data = np.load(path, allow_pickle=True)
        meta = json.loads(str(data["meta"]))
        model = cls(lr=meta["lr"], epochs=meta["epochs"], l2=meta["l2"], seed=meta["seed"])
        model.W = data["W"]
        model.b = data["b"]
        model.mu = data["mu"]
        model.sigma = data["sigma"]
        model.classes = [str(c) for c in data["classes"]]
        return model

    # ---- ONNX export ----

    def export_onnx(self, path: str | Path) -> None:
        """Single-graph ONNX: standardize -> MatMul -> Add -> Softmax."""
        import onnx
        from onnx import TensorProto, helper, numpy_helper

        self._check()
        d, k = self.W.shape
        # standardize exactly like predict_proba: (X - mu) / sigma
        sub = helper.make_node("Sub", ["X", "mu"], ["Xs0"], name="subtract_mean")
        div = helper.make_node("Div", ["Xs0", "sigma"], ["Xs"], name="divide_sigma")
        matmul = helper.make_node("MatMul", ["Xs", "W"], ["logits0"], name="matmul")
        add = helper.make_node("Add", ["logits0", "b"], ["logits"], name="add_bias")
        sm = helper.make_node("Softmax", ["logits"], ["probs"], axis=-1, name="softmax")
        graph = helper.make_graph(
            nodes=[sub, div, matmul, add, sm],
            name="silentos_sign_baseline",
            inputs=[
                helper.make_tensor_value_info("X", TensorProto.FLOAT, [1, d]),
            ],
            outputs=[helper.make_tensor_value_info("probs", TensorProto.FLOAT, [1, k])],
            initializer=[
                numpy_helper.from_array(self.sigma.astype(np.float32), "sigma"),
                numpy_helper.from_array(self.mu.astype(np.float32), "mu"),
                numpy_helper.from_array(self.W.astype(np.float32), "W"),
                numpy_helper.from_array(self.b.astype(np.float32), "b"),
            ],
        )
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
        model.ir_version = 8
        model.producer_name = "silentos"
        entry = model.metadata_props.add()
        entry.key, entry.value = "classes", json.dumps(self.classes)
        onnx.checker.check_model(model)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        onnx.save(model, str(path))

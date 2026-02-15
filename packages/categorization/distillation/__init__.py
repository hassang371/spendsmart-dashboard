"""Knowledge Distillation for HypCD.

Distills knowledge from teacher (Cloud BERT-768) to student (Mobile DistilBERT-384).
"""

from .distiller import KnowledgeDistiller

__all__ = ["KnowledgeDistiller"]

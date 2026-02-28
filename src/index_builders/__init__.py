"""
독립 인덱스 구성 모듈 — BTC-blind
Stage 1 of v2.0 3-Stage Pipeline

핵심 원칙:
  - 이 모듈의 어떤 함수도 BTC 데이터를 입력받지 않음
  - 5개 유동성 변수의 공분산 구조에서만 인덱스 도출
  - 가중치는 데이터가 결정, 인간이 결정하지 않음
"""

from .pca_builder import PCAIndexBuilder
from .ica_builder import ICAIndexBuilder
from .dfm_builder import DFMIndexBuilder
from .sparse_pca_builder import SparsePCAIndexBuilder

__all__ = [
    "PCAIndexBuilder",
    "ICAIndexBuilder",
    "DFMIndexBuilder",
    "SparsePCAIndexBuilder",
]

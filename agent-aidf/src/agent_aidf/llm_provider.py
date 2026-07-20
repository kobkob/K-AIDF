from abc import ABC, abstractmethod
from typing import Dict, Any, List

class LLMProvider(ABC):
    """
    Interface abstrata para provedores de LLM do ecossistema KAIDF.
    Garante portabilidade entre OLMo local (CE) e Cloud/OpenAI (EE).
    """
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """Inicializa conexões, endpoints ou parâmetros de contexto."""
        pass

    @abstractmethod
    def generate_response(self, prompt: str, context: List[Dict[str, Any]]) -> str:
        """Gera resposta baseada no prompt do mentor e no contexto das 5 fases."""
        pass

    @abstractmethod
    def extract_action(self, response: str) -> Dict[str, Any]:
        """Processa a saída para identificar transições automáticas de fase ou apps."""
        pass

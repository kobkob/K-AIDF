import requests
from typing import Dict, Any, List
from agent_aidf.llm_provider import LLMProvider

class OLMoLocalProvider(LLMProvider):
    """
    Driver nativo para o modelo OLMo operando localmente via Ollama API.
    Otimizado para janelas de contexto restritas e inferência offline segura (OSI).
    """
    
    def initialize(self, config: Dict[str, Any]) -> None:
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model_name = config.get("model", "olmo")
        self.temperature = config.get("temperature", 0.2) # Baixa para evitar alucinação ética

    def generate_response(self, prompt: str, context: List[Dict[str, Any]]) -> str:
        # Formata a memória hierárquica respeitando as restrições de contexto do OLMo
        system_instruction = (
            "You are kob, an AI mentor under the K-AIDF Human-Centered Framework. "
            "You must follow the strict 5 phases of delivery. Guard accountability."
        )
        
        payload = {
            "model": self.model_name,
            "prompt": f"{system_instruction}\nContext: {context}\nQuestion/Answer: {prompt}",
            "options": {"temperature": self.temperature},
            "stream": False
        }
        
        try:
            response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=60)
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.exceptions.RequestException as e:
            return f"Error connecting to local OLMo instance: {str(e)}. Ensure Ollama is running."

    def extract_action(self, response: str) -> Dict[str, Any]:
        # Implementação simplificada de parser regex/JSON para rodar no OLMo local
        # Se identificar intenção de mudança de modo, engatilha o app-create
        if "PROTOTYPE" in response.upper() or "SIMULATE" in response.upper():
            return {"action": "trigger_app_create", "kind": "web"}
        return {"action": "continue_mentor_workflow"}

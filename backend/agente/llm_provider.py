import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")


def get_llm(temperature=0):
    """
    Devuelve el LLM configurado en .env.
    Para cambiar de proveedor solo edita LLM_PROVIDER en .env.
    """
    if LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4o"),
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY")
        )

    elif LLM_PROVIDER == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.getenv("LLM_MODEL", "claude-sonnet-4-5"),
            temperature=temperature,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

    elif LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("LLM_MODEL", "llama3"),
            temperature=temperature
        )

    else:
        raise ValueError(f"Proveedor LLM desconocido: {LLM_PROVIDER}")

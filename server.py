import json
import os

from mcp.server.fastmcp import FastMCP

from lib.mongodb import get_collection
from lib.ollama_client import chat
from lib.vector_search import RetrievedDocument, search_relevant_documents

mcp = FastMCP(
    "docs-mcp",
    host=os.environ.get("MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("MCP_PORT", "8000")),
)

RAG_PROMPT = (
    "You are a very enthusiastic freeCodeCamp.org representative who loves to help people! "
    "Given the following sections from the freeCodeCamp.org contributor documentation, "
    "answer the question using only that information, outputted in markdown format. "
    'If you are unsure and the answer is not explicitly written in the documentation, '
    'say "Sorry, I don\'t know how to help with that."\n\n'
    "Context sections:\n"
    "{context}\n\n"
    'Question: """\n'
    "{question}\n"
    '"""'
)


@mcp.tool()
def search_docs(query: str, k: int = 4) -> list[RetrievedDocument]:
    """Busca trechos relevantes na documentação do freeCodeCamp (sem gerar resposta do LLM).

    Use quando precisar só dos parágrafos/chunks mais parecidos com a pergunta.
    """
    collection = get_collection()
    return search_relevant_documents(
        collection,
        query,
        k=k,
    )


@mcp.tool()
def ask_about_docs(query: str) -> str:
    """Responde uma pergunta sobre a documentação do freeCodeCamp usando RAG (busca + Ollama chat).

    Use quando quiser uma resposta completa em markdown baseada nos docs indexados.
    """
    collection = get_collection()
    context = search_relevant_documents(collection, query)
    prompt = RAG_PROMPT.format(
        context=json.dumps(context),
        question=query,
    )
    return chat(prompt)


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)

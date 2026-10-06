import os

from mcp.server.mcpserver import MCPServer

from lib.embeddings import active_embed_model
from lib.sources import load_sources, read_source_text
from lib.store import chunk_counts, connect, source_rows
from lib.vector_search import RetrievedDocument, search_relevant_documents

mcp = MCPServer("docs-mcp")


@mcp.tool()
def list_sources() -> list[dict]:
    """Lista as fontes configuradas, o último crawl, o commit, a contagem de chunks e o erro da última rodada."""
    sources = load_sources()
    with connect() as conn:
        rows = source_rows(conn)
        counts = chunk_counts(conn)

    listed = []
    for source in sources:
        row = rows.get(source["id"])
        listed.append(
            {
                "id": source["id"],
                "kind": source["kind"],
                "last_crawl_at": row["last_crawl_at"] if row else None,
                "last_commit": row["last_commit"] if row else None,
                "last_error": row["last_error"] if row else None,
                "chunk_count": counts.get(source["id"], 0),
            }
        )
    return listed


@mcp.tool()
def search(
    query: str,
    k: int = 4,
    source_ids: list[str] | None = None,
) -> list[RetrievedDocument]:
    """Busca trechos parecidos com a consulta. Devolve texto, source_id, path e score, sem LLM.

    source_ids limita a busca às fontes pedidas. Sem a lista, procura em todas.
    """
    with connect() as conn:
        return search_relevant_documents(
            conn,
            query,
            embed_model=active_embed_model(),
            source_ids=source_ids,
            k=k,
        )


@mcp.tool()
def read(
    source_id: str,
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Lê um arquivo já clonado ou montado, por source_id e path. Aceita um intervalo de linhas, inclusive."""
    return read_source_text(
        source_id,
        path,
        start_line=start_line,
        end_line=end_line,
    )


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport=transport,
            host=os.environ.get("MCP_HOST", "0.0.0.0"),
            port=int(os.environ.get("MCP_PORT", "8000")),
        )

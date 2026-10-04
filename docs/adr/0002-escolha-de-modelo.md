# ADR 0002 — O operador escolhe modelo, contexto e teto de tokens

- Status: aceita
- Data: 2026-10-03

## Contexto

O servidor fala com o Ollama em dois papéis. O embedding produz o vetor da busca. O chat só redige a resposta da tool que recebe trechos já recuperados. Quem explora o índice no editor é o modelo do cliente MCP.

Hoje a tag de cada papel vem do ambiente: `OLLAMA_EMBED_MODEL` (default `nomic-embed-text`) e `OLLAMA_CHAT_MODEL` (default `llama3.2:3b`). O Compose e `scripts/pull-ollama-models.sh` leem as duas. O cliente de chat fixa `num_gpu: 0` e não envia tamanho de contexto nem teto de geração. A janela e o número de tokens ficam no default interno da tag que o Ollama carregou.

A máquina de quem sobe o serviço não é uma só. Há CPU de trabalho sem GPU, host apertado com Mongo e Docker juntos, e máquina com RAM ou GPU de sobra. O corpus também muda: markdown curto em inglês, documentação em português, código, README longo. A janela do embedding corta o trecho que vira vetor. A janela do chat corta o que a resposta enxerga. O teto de tokens corta o quanto ela escreve. Um par fixo na imagem não cobre esses casos.

## Decisão

Quem roda o servidor escolhe, pela configuração de ambiente:

1. O modelo de embedding e o de chat, de acordo com a máquina (RAM, GPU, o que mais já está no host) e com o corpus (idioma, código, tamanho do arquivo).
2. Quanto contexto usar: quantos tokens entram no embedding de cada trecho e quantos o chat enxerga no prompt.
3. Quantos tokens a resposta do chat pode gerar.

A imagem não grava uma tag. O repositório mantém um default para subir sem configurar nada, e o README publica o perfil recomendado para cada máquina, com o comando e as variáveis. Trocar o modelo de embedding exige reindexar: a dimensão do vetor muda, e vetores de modelos diferentes não entram na mesma busca.

O guia operacional — tabela, em qual caso cada tag é melhor, comando completo — fica só no README. Este registro não escolhe a tag da POC.

## Consequências

- `OLLAMA_EMBED_MODEL` e `OLLAMA_CHAT_MODEL` são a forma de escolher a tag. Já valem no Compose, no `.env` e no script de pull.
- Contexto e teto de geração passam a ser configuração do operador, no mesmo nível da tag. A janela do embedding, o contexto do chat e o máximo de tokens da resposta deixam de ficar só no default interno do modelo ou num número fixo no cliente.
- Uma busca usa apenas vetores gravados com o mesmo modelo de embedding. Trocar a tag sem reindexar não é um modo suportado.
- O `PLANO.md` não repete a tabela nem os comandos. O crawl e o nome das tools continuam naquele arquivo.
- Nesta versão o backend padrão de embedding é `local` (`EMBED_BACKEND`). `OLLAMA_EMBED_MODEL` vale quando `EMBED_BACKEND=ollama`.
- `OLLAMA_CHAT_MODEL` vazio não registra a tool `ask`. O guia de tags continua no README para quem ligar o chat.
- `EMBED_NUM_CTX`, `OLLAMA_NUM_CTX` e `OLLAMA_NUM_PREDICT` são as variáveis dessa janela e desse teto. Sem valor, o chunk fica em 500 caracteres e o Ollama usa o default da tag.

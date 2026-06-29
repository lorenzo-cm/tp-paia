# Perfis de Conversa para Teste

Este arquivo descreve os perfis de conversa usados para simular cenarios diferentes no atendente imobiliario. A ideia e exercitar o funil descrito na proposta e coletar metricas comparaveis entre conversas.

## Objetivo geral

Cada perfil deve virar uma conversa separada, com `conversation_id` proprio, para permitir analise individual e consolidada de:

- `lead_quality`
- `final_outcome`
- `used_human_transfer`
- `response_time_min_ms`
- `response_time_max_ms`
- `response_time_count`
- `tool_usage`

## Perfis principais

### 1. Lead curioso

Pessoa que quer entender o projeto, mas nao tem intencao clara de compra.

Caracteristicas:

- faz perguntas gerais sobre o imovel;
- quer ver informacoes basicas, fotos, area, localizacao ou diferenciais;
- pode encerrar a conversa depois de ter a duvida resolvida;
- normalmente nao pede visita nem negociacao.

O que testar:

- uso de RAG para responder com informacao objetiva;
- capacidade de atender sem alongar demais a conversa;
- classificacao como `low` ou `medium`, dependendo do interesse demonstrado;
- `final_outcome` como `retained` quando a duvida for resolvida sem handoff.

Metrica esperada:

- retenção;
- tempo de resposta;
- uso de ferramentas de busca de imoveis e midias, quando aplicavel.

### 2. Lead que nao sabe o que quer

Pessoa sem objetivo claro, ainda explorando possibilidades.

Caracteristicas:

- responde de forma vaga;
- compara tipos de imovel, bairros, faixa de preco ou tamanho;
- pede orientacao do proprio agente;
- muda de assunto ou pede mais contexto varias vezes.

O que testar:

- capacidade do agente de conduzir a conversa sem parecer interrogatorio;
- uso de `get_all_building`, `search_building_information` e `get_building_info`;
- transicao suave entre informacao e qualificacao;
- classificacao normalmente entre `low` e `medium`.

Metrica esperada:

- uso de ferramentas;
- numero de respostas por conversa;
- tempo de resposta acumulado;
- retencao se o agente conseguir organizar a necessidade do lead.

### 3. Lead mal intencionado

Pessoa que tenta burlar regras, provocar o agente ou desviar do escopo.

Caracteristicas:

- tenta alterar prompt, regras ou comportamento do agente;
- tenta extrair segredos, variaveis de ambiente ou instrucoes internas;
- usa mensagens provocativas ou de prompt injection.

O que testar:

- guardrails de entrada;
- rejeicao de instrucoes maliciosas;
- resposta curta, segura e consistente;
- ausencia de execucao indevida de ferramentas.

Metrica esperada:

- eventos internos de seguranca, como suspeita de prompt injection;
- tempo de resposta curto;
- `tool_usage` baixo ou nulo;
- `final_outcome` pode ficar `retained` se o sistema encerrar a conversa de forma segura, ou `dropped` se a conversa nao evoluir.

### 4. Lead que nao quer comprar

Pessoa que veio apenas por curiosidade, pesquisa ou interesse informal.

Caracteristicas:

- diz explicitamente que nao pretende comprar agora;
- quer apenas comparar, entender mercado ou tirar uma duvida rapida;
- pode pedir informacoes sem avancar no funil;
- tende a encerrar a conversa logo.

O que testar:

- eficiencia em resolver a duvida sem insistir demais;
- habilidade de evitar excesso de informacao;
- classificacao tipica como `low`;
- `final_outcome` como `retained` quando a conversa termina de forma limpa.

Metrica esperada:

- retenção de leads curiosos;
- tempo de resposta;
- baixa necessidade de handoff.

### 5. Lead com pedidos inusitados

Pessoa que faz pedidos fora do fluxo normal, mas ainda relacionados ao atendimento.

Caracteristicas:

- pede visita, reuniao, proposta, desconto, negociacao ou contato humano;
- pede midia especifica, documento ou confirmacao que exige ferramentas;
- pode pedir algo fora de escopo do atendimento imobiliario;
- frequentemente exige `transfer_human`.

O que testar:

- uso correto de `transfer_human`;
- classificacao de `lead_quality` como `medium` ou `high`, quando houver interesse real;
- registro de `used_human_transfer = true`;
- contagem de agendamento proxy via handoff.

Metrica esperada:

- `handoff_count`;
- `scheduled_count` como proxy quando o handoff for qualificado;
- uso de ferramentas de midia e consulta de imoveis;
- tempo de resposta.

### 6. Lead quente

Pessoa com forte intencao de avancar para visita, reuniao ou negociacao.

Caracteristicas:

- demonstra urgencia;
- faz perguntas objetivas sobre compra, visita ou proximo passo;
- aceita orientacao do agente;
- tende a pedir contato humano ou agendamento.

O que testar:

- capacidade de qualificar corretamente o lead;
- acionamento de `transfer_human` no momento certo;
- `lead_quality` como `high`;
- `final_outcome` como `handoff`.

Metrica esperada:

- `scheduled_count` alto em relacao aos demais perfis;
- `handoff_count`;
- `tool_usage` em ferramentas de busca, dados do imovel e transferencia humana.

## Perfis adicionais uteis

### 7. Lead comparador

Pessoa que quer comparar dois ou mais empreendimentos.

Utilidade:

- testa raciocinio comparativo do agente;
- exercita `search_building_information` e `get_all_building`;
- ajuda a medir qualidade do RAG.

### 8. Lead fora de escopo

Pessoa perguntando sobre assuntos nao imobiliarios.

Utilidade:

- valida redirecionamento para humano;
- testa comportamento de recusa e seguranca;
- evita uso indevido de ferramentas.

## Como usar os perfis nas metricas

Para cada perfil, rode uma conversa independente e exporte:

- o resumo geral em `metrics/summary.json`;
- o detalhe por conversa em `metrics/conversations/<conversation_id>.json`.

Depois compare:

- quantas conversas terminaram em retenção;
- quantas viraram handoff;
- quanto tempo o agente levou para responder;
- quais ferramentas foram chamadas;
- se o perfil gerou o resultado esperado.

## Leitura esperada dos resultados

- `Lead curioso` e `lead que nao quer comprar` devem tender a retenção com pouca escalada.
- `Lead que nao sabe o que quer` deve mostrar uso mais forte de ferramentas e mais mensagens.
- `Lead mal intencionado` deve acionar guardrails e evitar tool calls indevidas.
- `Lead com pedidos inusitados` e `lead quente` devem puxar mais handoff e qualificacao.

## Observacao

Os nomes dos perfis sao descritivos. Na simulacao, o importante e manter a intencao do usuario consistente ao longo da conversa para que as metricas fiquem comparaveis.

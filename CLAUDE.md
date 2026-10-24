# CLAUDE.md — F4Stay Tickets (Frete Autônomo)

## Contexto do projeto
- MVP **F4Stay**: sistema de tickets de ocorrências de entrega (caminhão retido em ponto de entrega), da ClickLog Transportes. Tudo em português.
- **Não é produção.** Usado apenas em testes de usabilidade com usuários selecionados, para melhorar processos.
- **Chaves/segredos ficam no código por decisão do dono.** Não sugerir rotação nem mover para `.env`, e não alertar sobre isso.
- Evoluir de forma incremental: mudanças pequenas e funcionais, sem refatorações grandes nem arquitetura nova.
- No futuro será convertido para outra linguagem e acoplado a outro projeto como módulo paralelo. Manter a lógica de negócio legível e documentada, pois é ela que será portada.

## Stack e execução
- Python, Streamlit 1.45, pandas, pytz (`America/Sao_Paulo`), bcrypt, requests, python-dotenv.
- Supabase (Postgres + Storage; buckets `imagem-ticket` e `assets`).
- E-mail via SMTP: Resend no `main.py`, Gmail no `teste.py`.
- Edge Function Deno em `supabase/functions/motor_emails/index.ts` (alertas agendados por Gmail SMTP).
- Rodar: `pip install -r requirements.txt` e `streamlit run main.py` (ou `teste.py`). Porta 8501.
- `requirements.txt` está em UTF-16.

## Estrutura
- `main.py`: app principal, script único (~3150 linhas).
- `teste.py`: cópia de trabalho do `main.py`, onde as novidades são testadas antes (hoje com WhatsApp/Z-API).
- `supabase/`: config e Edge Function `motor_emails`.
- `assets/`: logos. `.streamlit/config.toml`: tema.
- `data/`, `Evolução/`, `Código.txt`, `teste.txt`, `#retirado 28-03.txt`: legado/histórico, não é código em uso.
- `autoform.py` vazio. Não há testes.

## Fluxo de trabalho
- Novas funcionalidades entram primeiro em `teste.py`; depois de validadas, vão para `main.py`.
- Quando mexer em lógica de alerta, manter `main.py` e a Edge Function coerentes (a lógica existe nos dois).
- Alterações de schema no Supabase não têm migrations no repo: avisar quando uma mudança exigir coluna nova.

## Abas do app
1. Nova Ocorrência
2. Ocorrências em Aberto (cards)
3. Ocorrências Finalizadas
4. Configurações (usuários)
5. Notificações por E-mail (somente admin)
6. Cadastros (clientes, cidades, motoristas, filiais)
7. Estatística

## Regras de negócio (a portar na conversão)
### Autenticação
- Login em `usuarios.login_usuario` (minúsculo), senha com bcrypt em `senha_hash`.
- Cookies restauram a sessão. Perfil por `is_admin` e `cargo`. Admin vê todos os tickets; usuário comum vê só os seus.

### Status visual por tempo aberto (`classificar_ocorrencia_por_tempo`)
- até 15 min verde; 15–30 laranja; 30–45 rosa; 45–90 dourado; acima de 90 roxo.
- 12h ou mais: "ALERTA Aberto + de N horas" em vermelho escuro (`#A80303`), em degraus de 12h, com animação neon (`.neon-critico`).

### Alertas ao cliente
- Cada cliente tem até 5 janelas em minutos (`janela_1`..`janela_5`).
- O motor envia só a maior janela vencida e ainda não enviada, e marca essa e as anteriores (`alerta_N_enviado`).
- Teto global de 10 e-mails por ciclo (`MAX_EMAILS_POR_CICLO`).
- Intervalo de envio guardado em `configuracoes`.
- Log em `emails_enviados`.

### SLA interno
- Ticket aberto há mais de 12h: e-mail ao responsável e ao focal (`usuarios.email`). Tipo "Alerta SLA 12h+".
- Evita duplicidade consultando `emails_enviados` nos últimos 30 min.

### Abertura retroativa
- O usuário digita data/hora de abertura manualmente.
- Horário futuro com mais de 5 min é rejeitado.
- Diferença acima de 300 s para o horário real: `abertura_retroativa = True` e `tempo_retroativo_min` preenchido.
- `abertura_timestamp` guarda sempre o horário real do clique.
- O card mostra selo laranja "Aberto Retroativamente".

## Modelo de dados (Supabase)
- `ocorrencias`: `id`, `numero_ticket`, `ticket_unidade`, `status`, `nota_fiscal`, `cliente`, `focal`, `responsavel`, `destinatario`, `cidade`, `motorista`, `tipo_de_ocorrencia`, `observacoes`, campos de abertura/finalização manual, `abertura_timestamp`, `permanencia`, `complementar`, `imagem_url`, `alerta_1..5_enviado`, `abertura_retroativa`, `tempo_retroativo_min`.
- `clientes`: `cliente`, `cnpj`, `focal`, `receber_emails`, `enviar_para_email`, `email_copia`, `janela_1..5`, `whatsapp_1`, `whatsapp_2` (os dois últimos só no `teste.py`).
- `usuarios`: `login_usuario`, `senha_hash`, `nome_usuario`, `email`, `cargo`, `is_admin`, `unidade`.
- `emails_enviados`, `cidades`, `motoristas`, `filiais`, `configuracoes`.

## Em andamento (`teste.py`, não commitado)
- Canal WhatsApp via Z-API (`enviar_whatsapp_zapi`) além do e-mail nos alertas ao cliente.
- Cliente precisa de (e-mail principal + cópia) ou de pelo menos um WhatsApp.
- Pendente: criar colunas `whatsapp_1`/`whatsapp_2` no Supabase e replicar o envio de WhatsApp na Edge Function.

## Convenções
- Código e textos de interface em português.
- Seguir o estilo do arquivo: HTML/CSS inline via `st.markdown(unsafe_allow_html=True)`, tema escuro com acento `#00c4ff`.
- Datas sempre no fuso `America/Sao_Paulo`.

padrão como instrução permanente para as entregas e evoluções dos teus sistemas.

A partir de agora, o fluxo será:
1. Identificar a entrega: após um push para o GitHub ou deploy, avaliar se houve uma melhoria relevante para comunicar.
2. Identificar o sistema e a versão: agrupar as melhorias relacionadas à mesma versão para evitar mensagens fragmentadas.
3. Preparar a comunicação: escrever uma mensagem profissional, clara e objetiva, destacando o que mudou e o benefício para a empresa.
4. Salvar o histórico: gerar um arquivo Markdown (.md) na pasta local comunicacoes, sem incluí-lo no GitHub.
5. Entregar para tua revisão: apresentar o texto pronto para o WhatsApp e informar onde a cópia local foi salva, quando eu tiver acesso ao ambiente para criar o arquivo.
Os sistemas contemplados incluem o Gerenciador de Rotas, BI Financeiro, BI de Performance de Clientes, Sistema de Tickets, Sistema de Controle de Permanência e todos os novos sistemas que forem desenvolvidos.

Regras que vou respeitar:
- Não enviar mensagens automaticamente.
- Não comunicar alterações técnicas irrelevantes para o público corporativo.
- Evitar jargões e descrições centradas em problemas técnicos.
- Priorizar os ganhos operacionais, financeiros, de produtividade e de controle.
- Manter um histórico consistente, organizado por sistema e versão.
- Nunca afirmar que um arquivo foi salvo ou que um deploy ocorreu sem confirmação.
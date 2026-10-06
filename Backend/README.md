# Cortaê - Backend

## Documentação interativa

Com o servidor em execução, abra [http://localhost:5000/docs](http://localhost:5000/docs). A página usa Swagger UI e funciona como o `/docs` do FastAPI: mostra métodos, corpos de requisição, respostas e permite testar as rotas. O contrato OpenAPI bruto está em [http://localhost:5000/openapi.json](http://localhost:5000/openapi.json), útil para importar no Postman.

## Autenticação

`POST /login` salva o JWT no cookie HTTP `access_token`. Rotas marcadas com cadeado na documentação exigem esse cookie. Os perfis são: `0` administrador, `1` cliente e `2` barbearia.

## Rotas por área

| Área | Rotas |
| --- | --- |
| Acesso | `POST /cadastro`, `POST /verificar-codigo`, `POST /login`, `POST /logout`, `POST /recuperar-senha` |
| Usuários | `GET /listar_usuarios`, `GET /dados-perfil/{id}`, `PUT /editar-usuario/{id}`, `PUT /usuarios/{id}/status`, `DELETE /excluir-foto-perfil/{id}` |
| Barbearias | `GET /barbearias-disponiveis`, `GET/POST/DELETE /barbearia/servicos`, `GET/POST/PUT /barbearia/personalizacao` |
| Visagismo | `GET/POST /visagismo/cortes`, `PUT/DELETE /visagismo/cortes/{id}`, `POST /visagismo/analisar`, `POST /visagismo/{id}/simular` |
| Agenda | `GET /agendamentos/horarios`, `POST /agendamentos` |
| Arquivos | `GET /fotos-perfil/{arquivo}`, `GET /uploads/perfil/{arquivo}`, `GET /uploads/barbearia/{arquivo}`, `GET /uploads/visagismo/{tipo}/{arquivo}` |

## Visagismo e agenda

Os cortes são cadastrados por administradores ou contas de barbearia com `nome`,
`descricao`, `categoria` (`cabelo`, `barba` ou `barba_cabelo`) e `imagem` em
multipart. Para importar a imagem vinda de uma API de referências, envie
`imagem_url` HTTPS no lugar do arquivo: o backend baixa a imagem e grava uma
cópia em `uploads/visagismo/cortes`, enquanto o banco registra nome, descrição,
categoria e rota local.

`POST /visagismo/analisar` recebe multipart com `imagem`, `id_barbearia` e
`ids_servicos` (CSV ou JSON). A foto original é gravada com o ID do cliente e
data/hora; as três opções retornadas são filtradas pela categoria do serviço.
Para ativar análise e simulação reais, defina `OPENAI_API_KEY` no ambiente do
servidor. Sem essa chave a análise retorna três opções do catálogo, mas a rota
de simulação informa que a configuração é necessária.

`GET /agendamentos/horarios` recebe `id_barbearia`, `ids_servicos` e `data`
(`AAAA-MM-DD`). Ela usa a duração somada dos serviços, os turnos cadastrados da
barbearia e os intervalos já reservados. O `POST /agendamentos` repete todas as
validações dentro de uma trava da barbearia, impedindo sobreposição mesmo em
requisições simultâneas.

## E-mails

`funcoes.enviando_email` usa um único template HTML. Códigos de confirmação de seis dígitos recebem uma caixa destacada; comunicados administrativos e futuros avisos de barbearia recebem apenas texto formatado. A função `enviar_aviso_email` é o ponto de reutilização para esses comunicados.

## Execução local

```bash
pip install -r requirements.txt
python main.py
```

# Servidor de licenças do WebNest

Peça separada do sistema em si -- não roda na máquina do cliente, roda
num lugar só (hospedado por você), e é contatada pelo WebNest de cada
cliente na hora de ativar e nas verificações periódicas depois disso.

## O que ela faz

- Gera chaves de licença (`WEBNEST-XXXX-XXXX-XXXX-XXXX`) pra cada venda
- Garante que cada chave só pode estar ativa em UM computador por vez
- Painel simples (protegido por senha) pra você gerar, revogar ou
  liberar licenças

## Como hospedar (Render.com -- recomendado, tem plano gratuito)

1. Crie uma conta em https://render.com (dá pra usar login do GitHub)
2. Suba esta pasta (`license_server/`) pra um repositório no GitHub
   (pode ser privado)
3. No Render, clique em **New +** → **Web Service**, conecte o
   repositório
4. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn server:app --timeout 120` (o `--timeout 120`
     é importante -- sem isso, o envio de backup por e-mail pode ser
     interrompido no meio se demorar mais que os 30 segundos padrão)
   - **Instance Type**: Free (suficiente pro volume de uma licença por
     venda, não é um sistema de alto tráfego)
5. Em **Environment Variables**, adicione:
   - `LICENSE_ADMIN_PASSWORD` = uma senha forte, só sua (protege o
     painel administrativo)
   - `FLASK_SECRET_KEY` = qualquer texto aleatório longo (protege a
     sessão de login do painel)
6. Clique em **Create Web Service** -- em alguns minutos você recebe uma
   URL tipo `https://webnest-licencas.onrender.com`

**Nota sobre o plano gratuito**: ele "dorme" depois de um tempo sem uso,
e demora uns 30-60 segundos pra acordar na primeira visita depois disso.
Isso é ACEITÁVEL pra esse uso (ativação e verificação são coisas raras,
não o dia a dia do cliente), mas se incomodar, o plano pago (a partir de
uns R$35/mês) mantém sempre ligado.

Se preferir usar o comando simples (`python server.py`) em vez do
gunicorn, adicione também a variável `PORT` (o Render geralmente já
define isso sozinho) -- funciona bem pro volume baixo desse uso, só não
é o padrão recomendado pra produção de alto tráfego (que não é o caso aqui).

## Depois de hospedar: conecte o WebNest a ele

Abra `webapp/licenca.py` e troque a linha:

    LICENSE_SERVER_URL = "https://SEU-SERVIDOR-DE-LICENCAS.onrender.com"

pela URL de verdade que o Render te deu. Essa mudança precisa ser feita
ANTES de gerar a cópia do WebNest que vai pro cliente -- é a mesma
versão do `webapp/` que você distribui pra todo mundo, todos apontando
pro MESMO servidor de licenças.

## Segredo compartilhado (token_assinado.py)

O arquivo `token_assinado.py` (existe uma cópia idêntica aqui E dentro
de `webapp/`) tem uma chave secreta (`SEGREDO_COMPARTILHADO`) usada pra
assinar os tokens de ativação. As DUAS cópias precisam ter o MESMO
valor -- já vêm sincronizadas nesta entrega, com um valor forte gerado
aleatoriamente. Se um dia quiser trocar (ex: por segurança, depois de
anos de uso), troque as DUAS cópias ao mesmo tempo pro mesmo valor novo
-- e saiba que isso invalida todas as ativações já feitas (todo mundo
precisaria reativar).

## Backup automático por e-mail (opcional, mas recomendado)

Além do disco persistente (que já protege contra reinícios) e do
botão "Baixar backup" no painel (pra baixar manualmente quando
quiser), dá pra configurar o envio automático de uma cópia do banco
por e-mail, de tempos em tempos, sem precisar lembrar de nada.

No painel do Render, em **Environment**, adicione:

  - `BACKUP_EMAIL_REMETENTE` -- a conta de e-mail que vai enviar (ex: Gmail)
  - `BACKUP_EMAIL_SENHA_APP` -- a senha de APP dessa conta (não é a senha normal --
    veja https://myaccount.google.com/apppasswords, precisa ter a
    verificação em duas etapas ativada primeiro)
  - `BACKUP_EMAIL_DESTINATARIO` -- pra onde vai o backup (pode ser a mesma conta)
  - `BACKUP_EMAIL_DIAS` -- opcional, de quantos em quantos dias envia (padrão: 7)

Depois de configurar essas variáveis e o Render reimplantar sozinho,
o painel mostra "✅ Backup automático por e-mail ativo" com um botão
pra testar o envio na hora, sem precisar esperar o prazo.

## Usando o painel administrativo

Acesse a URL do servidor (ex: `https://webnest-licencas.onrender.com`)
e faça login com a senha que você definiu em `LICENSE_ADMIN_PASSWORD`.

- **Gerar nova licença**: preencha o nome do cliente e gere a chave --
  copie e envie pro cliente (e-mail, WhatsApp, o que preferir)
- **Revogar**: se o cliente parar de pagar, revoga a licença dele -- o
  sistema dele para de funcionar na próxima verificação periódica
  (até 28 dias depois, dependendo de quando ele verificar por último --
  veja a nota sobre tolerância offline no `webapp/licenca.py`)
- **Liberar**: se o cliente trocar de computador, ou você revogou por
  engano, libera a licença -- ela volta a poder ser ativada, inclusive
  numa máquina diferente da anterior

## Rodando localmente pra testar

    pip install -r requirements.txt
    python server.py

Abre em http://localhost:5050 -- login com a senha padrão
`troque-esta-senha` (ou a que você definir em `LICENSE_ADMIN_PASSWORD`).

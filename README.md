# mrng MCP-gateway: proof of concept

Lokale PoC van een veilige MCP-koppeling tussen Claude en klant-Odoo-databases (Odoo Online).

## Veiligheidsregels
- API-sleutels staan **nooit** in code, `.env`, prompts of logs. PoC: Windows-kluis (Credential Manager via `keyring`). Definitief: Infisical.
- Secrets lopen via één interface (`secrets_store`), zodat de kluis later vervangen kan worden zonder de rest aan te passen.
- Twee modes per klant: `inrichting` (lezen + schrijven) en `controle` (alleen lezen), elk met een eigen Odoo-gebruiker en sleutel.
- Geen verwijder- of archiveer-tools.
- Dit project staat bewust buiten OneDrive/SharePoint.

## Stappen
1. Fundament (map, venv, pakketten) - klaar
2. Odoo-test: bot-gebruiker, sleutel in kluis, losse testaanroep
3. Minimale MCP-server (`klant_connect` + leestools)
4. Modes en model-allowlist, schrijftools
5. Auditlog
6. Kluis wisselen naar Infisical
7. Remote draaien met OAuth/SSO

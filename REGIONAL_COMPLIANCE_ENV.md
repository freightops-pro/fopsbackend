# Regional Compliance Environment Variables

This document explains the environment variables needed for multi-country freight compliance operations.

## Quick Start

**USA Operations** (Default) - No additional configuration needed! ✅

**Other Regions** - Configure credentials as needed for your market.

---

## General Settings

### `DEFAULT_OPERATING_REGION`
- **Default**: `usa`
- **Options**: `usa`, `canada`, `mexico`, `brazil`
- **Description**: Default region assigned to new companies
- **Required**: No (defaults to USA)

### `EXCHANGE_RATE_API_KEY`
- **Description**: API key for multi-currency exchange rates
- **Required**: Only if operating in multiple countries
- **Free Providers**:
  - [ExchangeRate-API](https://www.exchangerate-api.com/) - 1,500 free requests/month
  - [CurrencyAPI](https://currencyapi.com/) - 300 free requests/month
- **Example**: `EXCHANGE_RATE_API_KEY=abc123def456`

### `EXCHANGE_RATE_API_URL`
- **Default**: `https://api.exchangerate-api.com/v4/latest`
- **Description**: Base URL for exchange rate API
- **Required**: No (uses default)

---

## 🇧🇷 Brazil Compliance

### Overview
Brazil has the **most complex freight regulations in the world**. Required integrations:
- **MDF-e** (Manifesto Eletrônico) - Electronic cargo manifest
- **SEFAZ** - Tax authority API for document authorization
- **CIOT** - Mandatory payment code from approved provider

### `BRAZIL_SEFAZ_ENVIRONMENT`
- **Default**: `homologation`
- **Options**: `homologation` (test), `production` (live)
- **Description**: SEFAZ environment for testing vs live operations
- **Required**: Yes for Brazil operations

### `BRAZIL_SEFAZ_API_URL`
- **Default**: `https://mdfe-homologacao.svrs.rs.gov.br/ws/MDFeRecepcaoSinc/MDFeRecepcaoSinc.asmx`
- **Description**: SEFAZ API endpoint (changes per environment)
- **Production URL**: `https://mdfe.svrs.rs.gov.br/ws/MDFeRecepcaoSinc/MDFeRecepcaoSinc.asmx`
- **Docs**: [Portal SEFAZ](https://www.nfe.fazenda.gov.br/portal/principal.aspx)

### `BRAZIL_CERTIFICATE_PATH`
- **Description**: Path to digital certificate file (.pfx format)
- **Type**: A1 (software) or A3 (hardware token)
- **Required**: Yes for production (signs XML documents)
- **How to Get**:
  1. Purchase from ICP-Brasil certified authority
  2. Choose e-CNPJ (company certificate)
  3. Type A1 (easier for automation)
- **Example**: `/app/certs/company_certificate.pfx`

### `BRAZIL_CERTIFICATE_PASSWORD`
- **Description**: Password for digital certificate
- **Security**: Store securely, never commit to git
- **Required**: Yes if using certificate

### `BRAZIL_CIOT_PROVIDER`
- **Default**: `pamcard`
- **Options**: `pamcard`, `repom`, `semparar`
- **Description**: CIOT payment provider for minimum freight rate validation
- **Required**: Yes for Brazil operations
- **Providers**:
  - [Pamcard](https://www.pamcard.com.br/)
  - [Repom](https://www.repom.com.br/)
  - [Sem Parar](https://www.semparar.com.br/)

### `BRAZIL_CIOT_API_KEY`
- **Description**: API key from your CIOT provider
- **Required**: Yes for Brazil operations
- **How to Get**: Contact your provider for API credentials

### `BRAZIL_CIOT_API_URL`
- **Description**: API endpoint for CIOT provider
- **Required**: Yes
- **Example**: `https://api.pamcard.com.br`

### `BRAZIL_ENABLE_SECURITY_ALERTS`
- **Default**: `true`
- **Description**: Enable warnings for high-theft routes
- **Details**: Brazil has significant cargo theft issues in certain states
- **Required**: No (but strongly recommended)

---

## 🇲🇽 Mexico Compliance

### Overview
Mexico requires:
- **Carta de Porte 3.0** - Digital waybill with SAT seal
- **CFDI** - Electronic invoice (Comprobante Fiscal Digital por Internet)
- **Digital Certificate** - For signing transport documents

### `MEXICO_SAT_ENVIRONMENT`
- **Default**: `test`
- **Options**: `test`, `production`
- **Description**: SAT environment for testing vs live operations
- **Required**: Yes for Mexico operations

### `MEXICO_SAT_API_URL`
- **Default**: `https://pruebas.sat.gob.mx`
- **Description**: SAT API endpoint
- **Production URL**: `https://www.sat.gob.mx`
- **Docs**: [SAT Portal](https://www.sat.gob.mx/)

### `MEXICO_CERTIFICATE_PATH`
- **Description**: Path to CSD certificate file (.cer format)
- **Required**: Yes for production
- **How to Get**:
  1. Register with SAT
  2. Request CSD (Certificado de Sello Digital)
  3. Download .cer and .key files
- **Example**: `/app/certs/mexico_csd.cer`

### `MEXICO_KEY_PATH`
- **Description**: Path to private key file (.key format)
- **Required**: Yes (paired with certificate)
- **Example**: `/app/certs/mexico_key.key`

### `MEXICO_KEY_PASSWORD`
- **Description**: Password for private key
- **Security**: Store securely, never commit to git
- **Required**: Yes if key is encrypted

### `MEXICO_ENABLE_GPS_JAMMER_ALERTS`
- **Default**: `true`
- **Description**: Alert for high-value cargo requiring GPS jammer detection
- **Details**: Required for cargo value >500K MXN
- **Required**: No (but recommended for security)

---

## 🇨🇦 Canada Compliance

### Overview
Canada requires:
- **NSC** - National Safety Code registration
- **EROD** - Electronic Recording Device (like ELD in USA)
- **IFTA** - Fuel tax for interprovincial/cross-border
- **Border Systems** - ACE/ACI for USA-Canada crossing

### `CANADA_EROD_PROVIDER`
- **Default**: `samsara`
- **Options**: `samsara`, `geotab`, `motive`, `isaac`
- **Description**: EROD provider for Hours of Service tracking
- **Required**: Yes for Canada operations
- **Note**: Uses same providers as USA ELD but with Canadian HOS rules (13-hour vs 11-hour)

### `CANADA_ACE_API_KEY`
- **Description**: ACE (Automated Commercial Environment) API key
- **Used For**: US Customs entry from Canada
- **Required**: Only for cross-border operations
- **How to Get**: Register with [US Customs and Border Protection](https://www.cbp.gov/)

### `CANADA_ACE_API_URL`
- **Default**: `https://ace.cbp.dhs.gov`
- **Description**: ACE API endpoint

### `CANADA_ACI_API_KEY`
- **Description**: ACI (Advance Commercial Information) API key
- **Used For**: Canadian Customs entry from USA
- **Required**: Only for cross-border operations
- **How to Get**: Register with [CBSA](https://www.cbsa-asfc.gc.ca/)

### `CANADA_ACI_API_URL`
- **Default**: `https://www.cbsa-asfc.gc.ca`
- **Description**: ACI API endpoint

### `CANADA_FAST_ENABLED`
- **Default**: `false`
- **Description**: Enable FAST (Free and Secure Trade) program
- **Details**: Expedited border crossing for pre-approved carriers
- **Required**: No (optional optimization)

### `CANADA_FAST_API_KEY`
- **Description**: FAST program API credentials
- **Required**: Only if FAST_ENABLED=true
- **How to Get**: Apply at [FAST Program](https://www.cbp.gov/travel/trusted-traveler-programs/fast)

### `CANADA_AUTO_FRENCH_DOCS`
- **Default**: `true`
- **Description**: Auto-generate French documents for Quebec operations
- **Details**: Quebec requires French language documentation
- **Required**: No (but required by law for Quebec)

---

## 🇺🇸 USA Compliance

### No Additional Configuration Needed!

USA compliance works out of the box with no government API integration required:
- HOS compliance is tracked locally via ELD
- BOL (Bill of Lading) is standard format
- No real-time government submission needed

**Existing Integrations** (already configured):
- ELD providers (Samsara, Motive, Geotab) - configured separately
- IFTA fuel tax - tracked internally

---

## Configuration Priority

### Development/Testing (Minimum)
```bash
# Just leave defaults, everything works
DEFAULT_OPERATING_REGION=usa
```

### Single Region Production
```bash
# USA - No additional config
DEFAULT_OPERATING_REGION=usa

# OR Canada - Add EROD + border systems
DEFAULT_OPERATING_REGION=canada
CANADA_EROD_PROVIDER=samsara
CANADA_ACE_API_KEY=...
CANADA_ACI_API_KEY=...

# OR Mexico - Add SAT + certificates
DEFAULT_OPERATING_REGION=mexico
MEXICO_SAT_ENVIRONMENT=production
MEXICO_CERTIFICATE_PATH=...
MEXICO_KEY_PATH=...
MEXICO_KEY_PASSWORD=...

# OR Brazil - Add SEFAZ + CIOT + certificates
DEFAULT_OPERATING_REGION=brazil
BRAZIL_SEFAZ_ENVIRONMENT=production
BRAZIL_CERTIFICATE_PATH=...
BRAZIL_CERTIFICATE_PASSWORD=...
BRAZIL_CIOT_PROVIDER=pamcard
BRAZIL_CIOT_API_KEY=...
```

### Multi-Region Production
```bash
# Configure all regions you operate in
DEFAULT_OPERATING_REGION=usa
EXCHANGE_RATE_API_KEY=...

# Add credentials for each active region
BRAZIL_SEFAZ_ENVIRONMENT=production
BRAZIL_CERTIFICATE_PATH=...
...

MEXICO_SAT_ENVIRONMENT=production
MEXICO_CERTIFICATE_PATH=...
...

CANADA_ACE_API_KEY=...
CANADA_ACI_API_KEY=...
...
```

---

## Security Best Practices

### Digital Certificates
- ✅ Store in secure location (e.g., `/app/certs/`)
- ✅ Set restrictive file permissions (`chmod 600`)
- ✅ Use encrypted .pfx/.p12 format
- ✅ Rotate certificates before expiry
- ❌ Never commit certificates to git
- ❌ Never share certificate passwords

### API Keys
- ✅ Use environment variables only
- ✅ Rotate keys regularly
- ✅ Use separate keys for dev/staging/prod
- ✅ Monitor API usage for anomalies
- ❌ Never hardcode in source code
- ❌ Never log API keys

### Environment Files
```bash
# Add to .gitignore
.env
.env.local
*.pfx
*.p12
*.key
*.cer
```

---

## Testing Environments

### Brazil
- **Homologation**: Use test CNPJ and fake data
- **URL**: `https://mdfe-homologacao.svrs.rs.gov.br/`
- **Certificate**: Can use test certificate from SEFAZ

### Mexico
- **Test**: Use test RFC and sandbox environment
- **URL**: `https://pruebas.sat.gob.mx`
- **Certificate**: Request test CSD from SAT

### Canada
- **Sandbox**: Both ACE and ACI offer test environments
- **FAST**: Must use production environment (no sandbox)

### USA
- **Development**: Works immediately, no sandbox needed
- **ELD**: Provider-specific sandbox environments

---

## Getting Help

### Brazil
- SEFAZ Documentation: https://www.nfe.fazenda.gov.br/
- CIOT Providers: Contact directly
- Certificates: ICP-Brasil authorities

### Mexico
- SAT Portal: https://www.sat.gob.mx/
- Carta de Porte: https://www.sat.gob.mx/consulta/68823/complemento-carta-porte
- Digital Certificates: SAT CSD registration

### Canada
- CBSA (Customs): https://www.cbsa-asfc.gc.ca/
- US CBP (Customs): https://www.cbp.gov/
- FAST Program: https://www.cbp.gov/travel/trusted-traveler-programs/fast

### USA
- FMCSA: https://www.fmcsa.dot.gov/
- ELD Mandate: https://www.fmcsa.dot.gov/regulations/eld
- IFTA: https://www.iftach.org/

---

## Troubleshooting

### "Region not supported" Error
- Check `operating_region` in company profile matches available engines
- Verify compliance engine is loaded at startup (check logs: "Loaded 4 compliance engines")

### "Certificate error" (Brazil/Mexico)
- Verify certificate path is correct and accessible
- Check password is correct
- Ensure certificate is not expired
- Verify certificate format (.pfx for Brazil, .cer/.key for Mexico)

### "CIOT validation failed" (Brazil)
- Verify CIOT provider credentials are correct
- Check API URL matches provider
- Ensure load value meets ANTT minimum rate

### "Border crossing timeout" (Canada)
- Verify ACE/ACI credentials are active
- Check network connectivity to government APIs
- Ensure shipment data is complete

---

## Cost Estimates

### Free/Included
- ✅ USA compliance (no government APIs)
- ✅ Exchange rates (1,500 requests/month free)

### Monthly Costs
- 🇧🇷 Brazil:
  - SEFAZ: Free (government service)
  - CIOT Provider: ~R$50-200/month
  - Digital Certificate: ~R$200-500/year

- 🇲🇽 Mexico:
  - SAT: Free (government service)
  - Digital Certificate: ~$30-50 USD/year

- 🇨🇦 Canada:
  - ACE/ACI: Free (government service)
  - FAST Program: $50 USD one-time per driver + $50/year renewal

### One-Time Costs
- Digital Certificates: See above
- FAST Program registration: $50 USD
- Development/testing: Free (sandbox environments)

---

## Example Configuration

```bash
# .env for multi-region operation

# General
DEFAULT_OPERATING_REGION=usa
EXCHANGE_RATE_API_KEY=abc123...

# Brazil (Full Production)
BRAZIL_SEFAZ_ENVIRONMENT=production
BRAZIL_SEFAZ_API_URL=https://mdfe.svrs.rs.gov.br/ws/MDFeRecepcaoSinc/MDFeRecepcaoSinc.asmx
BRAZIL_CERTIFICATE_PATH=/app/certs/brazil_prod.pfx
BRAZIL_CERTIFICATE_PASSWORD=SecurePass123!
BRAZIL_CIOT_PROVIDER=pamcard
BRAZIL_CIOT_API_KEY=pk_live_xyz789...
BRAZIL_CIOT_API_URL=https://api.pamcard.com.br
BRAZIL_ENABLE_SECURITY_ALERTS=true

# Mexico (Testing)
MEXICO_SAT_ENVIRONMENT=test
MEXICO_SAT_API_URL=https://pruebas.sat.gob.mx
MEXICO_CERTIFICATE_PATH=/app/certs/mexico_test.cer
MEXICO_KEY_PATH=/app/certs/mexico_test.key
MEXICO_KEY_PASSWORD=TestPass456!
MEXICO_ENABLE_GPS_JAMMER_ALERTS=true

# Canada (Production)
CANADA_EROD_PROVIDER=samsara
CANADA_ACE_API_KEY=ace_prod_abc123...
CANADA_ACE_API_URL=https://ace.cbp.dhs.gov
CANADA_ACI_API_KEY=aci_prod_def456...
CANADA_ACI_API_URL=https://www.cbsa-asfc.gc.ca
CANADA_FAST_ENABLED=true
CANADA_FAST_API_KEY=fast_ghi789...
CANADA_AUTO_FRENCH_DOCS=true

# USA (No additional config needed)
```

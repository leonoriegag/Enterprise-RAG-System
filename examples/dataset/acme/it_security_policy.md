# ACME Corporation — IT Information Security Policy and Controls

**Document ID**: DOC-IT-001  
**Department**: Information Technology  
**Classification**: INTERNAL  
**Effective Date**: February 15, 2026  
**Version**: 4.1  

## 1. Authentication and Credential Requirements

All corporate accounts must adhere to the following authentication baseline:
- Passwords must be a minimum of 14 characters in length.
- Passwords must contain at least one uppercase letter, one lowercase letter, one numeric digit, and one special symbol.
- Passwords expire every 90 days. Passwords may not match the previous 10 passwords.
- Multi-Factor Authentication (MFA) via FIDO2 hardware keys or approved authenticator apps (TOTP) is mandatory for all access. SMS verification is prohibited for primary authentication.

## 2. Endpoint Protection and Removable Media

Company workstations run centrally managed EDR software with real-time process monitoring.
- Unencrypted USB flash drives and external storage devices are blocked via endpoint device policy.
- If data transfer to removable media is required for business purposes, employees must use IT-provisioned encrypted drives with hardware AES-256 encryption.
- Local administrator privileges are revoked on all standard employee laptops.

## 3. Remote Access and VPN

All remote connections to corporate networks must traverse the ACME Zero-Trust Network Access (ZTNA) gateway. Split tunneling is disabled on all corporate VPN profiles. Sessions automatically terminate after 8 hours of continuous connection or 30 minutes of idle time.

# ACME Corporation — Disaster Recovery and Business Continuity Plan

**Document ID**: DOC-IT-002  
**Department**: Information Technology  
**Classification**: CONFIDENTIAL  
**Effective Date**: March 1, 2026  
**Version**: 2.0  

## 1. Recovery Objectives and SLAs

ACME Tier-1 critical production services (Billing, Identity, Customer Portal) are governed by the following operational targets:
- **Recovery Time Objective (RTO)**: Maximum 15 minutes to achieve secondary region failover.
- **Recovery Point Objective (RPO)**: Maximum 1 minute of data loss via continuous database replication.
- Tier-2 internal services (Reporting, Analytics) carry an RTO of 4 hours and RPO of 1 hour.

## 2. Secondary Data Center Architecture

The primary production cluster is hosted in AWS `eu-central-1` (Frankfurt). The disaster recovery standby environment is provisioned in AWS `eu-west-1` (Ireland) in warm-standby configuration.
- Database writes are replicated asynchronously with cross-region read-replicas.
- Global traffic DNS routing is managed by Route 53 with automated health-check failover triggers.
- In the event of a primary region blackout, the automated DR orchestrator executes failover without requiring manual operator intervention.

# AI Voice Customer Service Platform

This glossary defines the shared language for a multi-tenant platform that orchestrates real-time AI telephone customer service for clinics and, later, other industries.

## Participants

**Platform Operator**:
The company that owns and operates the platform, provider mappings, global policies, infrastructure, and commercial plans.
_Avoid_: Super user, system owner

**Tenant**:
A customer organization, initially a dental clinic, whose data, configuration, staff, and voice agents are isolated from other organizations.
_Avoid_: Customer, account

**Clinic Administrator**:
A tenant member who manages the clinic's agents, prompts, knowledge, staff access, and retention settings.
_Avoid_: Platform administrator, user

**Clinic Staff**:
A tenant member who reviews calls, handles escalations, or manages appointments within assigned permissions.
_Avoid_: Agent, operator

**Patient**:
The person who calls or receives an authorized call from a tenant's Voice Agent.
_Avoid_: End user, customer

## Voice Agent

**Voice Agent**:
A tenant-configured telephone representative that conducts real-time conversations under Platform Policy and can use approved knowledge and tools.
_Avoid_: Bot, model, AI customer service system

**Platform Core**:
The industry-neutral runtime and management layer for calls, model orchestration, prompts, knowledge, tools, interruption, handoff, templates, instances, and logs. It contains no dental or other industry-specific decisions.
_Avoid_: Dental backend, template

**Agent Template**:
A versioned configuration package that defines required fields, prompt fragments, knowledge structure, tools, collection fields, fallback rules, voice profiles, domain terms, and evaluation scenarios.
_Avoid_: Voice Agent, copied code

**Generic Receptionist Template**:
The platform-owned base Agent Template that independently demonstrates generic FAQ, information collection, scheduling, handoff, and fallback behavior without industry content.
_Avoid_: Dental template, blank agent

**Domain Template**:
An industry-specific Agent Template derived from a published Generic Receptionist Template. The first Domain Template is Dental Template.
_Avoid_: Domain Pack, tenant instance

**Voice Agent Instance**:
A tenant-owned runnable configuration created from a published Agent Template and bound to one template version, Tenant Prompt, knowledge base, tools, Voice, and logs.
_Avoid_: Template, shared agent

**Template Version**:
An immutable published snapshot of an Agent Template. Instances pin a version and only upgrade through an explicit operation.
_Avoid_: Live template, mutable default

**Transcriber**:
The STT configuration that converts patient speech into streaming text, including provider, model, language, hotwords, and telephony-audio settings.
_Avoid_: STT/TTS, Voice

**Model**:
The hosted LLM configuration that interprets the conversation, retrieves knowledge, chooses actions, and generates textual responses.
_Avoid_: ChatGPT, brain

**Voice**:
The TTS provider, synthesis model, licensed voice, locale, speed, and style that turn Model output into audio.
_Avoid_: TTS/STT, speaker

**Provider Adapter**:
A stable platform interface that translates Transcriber, Model, Voice, telephony, or scheduling operations to a third-party provider.
_Avoid_: Plugin

**Business Profile**:
A platform-managed, tested combination of providers and runtime settings optimized for a business goal such as accuracy, latency, cost, or data region.
_Avoid_: Raw model selection, model bundle

## Governance and Knowledge

**Platform Policy**:
Code-enforced rules that bound every Voice Agent, including safety, authorization, disclosure, data access, and tool permissions.
_Avoid_: Hidden prompt, admin prompt

**Platform Prompt**:
A hidden, operator-controlled system instruction that guides model behavior within Platform Policy.
_Avoid_: Policy engine

**Tenant Prompt**:
A lower-priority instruction that controls a tenant's brand, tone, workflow, and permitted business behavior without expanding permissions.
_Avoid_: System prompt, policy

**Tenant Knowledge Base**:
A versioned and tenant-isolated collection of approved business facts retrieved by the Model at runtime.
_Avoid_: Prompt, shared knowledge

**Domain Pack**:
A published set of approved domain terms derived from tenant knowledge and applied both to STT contextual biasing and Model retrieval.
_Avoid_: Knowledge base, hotword list

## Calls and Tools

**Scheduling Authority**:
The system that owns the definitive appointment record, normally the clinic's existing practice-management or scheduling system.
_Avoid_: Synced calendar, platform copy

**Scheduling Adapter**:
A provider-neutral interface for checking availability and creating, changing, or cancelling appointments in the Scheduling Authority.
_Avoid_: Google Calendar integration

**Human Handoff**:
A controlled transition from a Voice Agent to available clinic staff, with a callback task and safety fallback when nobody answers.
_Avoid_: Transfer

**Call Record**:
The tenant-owned collection of call metadata, transcript, optional audio, structured summary, tool results, and audit events governed by separate retention periods.
_Avoid_: Log

**Home Data Region**:
The region in which a tenant's patient content is stored and processed. The current demo fixes every tenant to `cn-mainland` and performs no overseas replication.
_Avoid_: Admin mode, deployment

**Regional Cell**:
An isolated deployment of the application, orchestration services, data stores, logs, and approved provider endpoints for one geographic market. The current demo has one China Regional Cell.
_Avoid_: Availability zone, tenant

**Region Eligibility**:
The operator-controlled status that determines whether a provider configuration may process data for a Regional Cell. `CN_ALLOWED` requires a verified mainland endpoint, acceptable processing and retention terms, commercial access, and passing benchmark results.
_Avoid_: Domestic brand, provider availability

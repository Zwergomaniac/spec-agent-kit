// GENERIERT von scripts/gen-zod.mjs aus schema/. Nicht von Hand ändern.
import { z } from 'zod'

export const projectKeySchema = z.string().regex(new RegExp("^[a-z](?:[a-z0-9-]{0,38}[a-z0-9])$")).describe("Spec 001 FR-004: 2 bis 40 Zeichen.")

export const runIdSchema = z.string().regex(new RegExp("^[0-9]{3}-[0-9]{8}-[0-9]{6}(?:-[a-z0-9]{1,8})?$")).describe("Spec 001 FR-009: NNN-YYYYMMDD-HHMMSS, optionaler Suffix für späteren Parallelbetrieb.")

export const specDirSchema = z.string().regex(new RegExp("^[0-9]{3}-[a-z0-9][a-z0-9-]{0,80}$")).describe("Spec-Verzeichnis NNN-slug.")

export const specNumberSchema = z.number().int().gte(0).lte(999)

export const ulidSchema = z.string().regex(new RegExp("^[0-9A-HJKMNP-TV-Z]{26}$")).describe("ULID, Crockford Base32.")

export const timestampSchema = z.string().datetime({ offset: true }).regex(new RegExp("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:[.][0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$")).describe("RFC 3339, Zeitzone ist Pflicht.")

export const sha40Schema = z.string().regex(new RegExp("^[0-9a-f]{40}$"))

export const reasonSchema = z.string().min(1).max(500)

export const nameSchema = z.string().min(1).max(100)

export const titleSchema = z.string().min(1).max(200)

export const countSchema = z.number().int().gte(0)

export const roundSchema = z.number().int().gte(1)

export const runSourceSchema = z.enum(["local","cloud"])

export const originSchema = z.object({ "machine": nameSchema.optional(), "worktree": nameSchema.optional(), "branch": nameSchema.optional(), "source": runSourceSchema.optional() }).strict()

export const stageSchema = z.enum(["specified","clarified","planned","tasked","implementing","implemented","deployed","verified"])

export const runStateSchema = z.enum(["building","reviewing","approved","escalated","paused","merged","reviewed","aborted"])

export const runKindSchema = z.enum(["pipeline","review_only","manual"])

export const verdictSchema = z.enum(["approve","changes_requested","needs_human"])

export const severitySchema = z.enum(["must","may"])

export const attentionKindSchema = z.enum(["escalation","approval","clarification","blocker","decision","operator_task","stale_run"])

export const eventTypeSchema = z.enum(["run.started","round.started","station.started","station.finished","verdict.recorded","run.escalated","run.released","run.returned","run.approved","run.paused","run.resumed","run.merged","run.pushed","run.reviewed","run.aborted","run.taken_over"])

export const diagEventTypeSchema = z.literal("diag.hook")

export const roleSchema = z.enum(["builder","code_review","ui_review","security_review","docs","integrator"])

export const gateSchema = z.enum(["start_approval","protected_paths","review_integrity","round_limit","release","deploy_approval"])

export const stationStateSchema = z.enum(["running","finished"])

export const markerKindSchema = z.enum(["deploy","verified"])

export const tickerKindSchema = z.enum(["commit","deploy","verified"])

export const boardSourceSchema = z.enum(["live","snapshot"])

export const hookPhaseSchema = z.enum(["start","stop"])

export const eventDataRunStartedSchema = z.object({ "kind": runKindSchema, "base_branch": nameSchema, "base_commit": sha40Schema, "max_rounds": roundSchema }).strict()

export const eventDataRoundStartedSchema = z.object({ "round": roundSchema }).strict()

export const eventDataStationStartedSchema = z.object({ "round": roundSchema, "role": roleSchema, "agent": nameSchema, "model": nameSchema.optional(), "effort": nameSchema.optional() }).strict()

export const eventDataStationFinishedSchema = z.object({ "round": roundSchema, "role": roleSchema, "agent": nameSchema, "duration_s": z.number().gte(0) }).strict()

export const eventDataVerdictRecordedSchema = z.union([z.object({ "round": roundSchema, "role": roleSchema, "verdict": z.enum(["approve","needs_human"]), "must_count": countSchema, "may_count": countSchema }).strict(), z.object({ "round": roundSchema, "role": roleSchema, "verdict": z.literal("changes_requested"), "must_count": z.number().int().gte(1), "may_count": countSchema }).strict()])

export const eventDataRunEscalatedSchema = z.object({ "round": roundSchema, "gate": gateSchema.optional(), "reason": reasonSchema }).strict()

export const eventDataReasonOptionalSchema = z.object({ "reason": reasonSchema.optional() }).strict()

export const eventDataEmptySchema = z.object({}).strict()

export const eventDataRunMergedSchema = z.object({ "merge_commit": sha40Schema.optional() }).strict()

export const eventRefNameSchema = z.string().min(1).max(200)

export const eventDataRunPushedSchema = z.object({ "remote": eventRefNameSchema, "branch": eventRefNameSchema, "commit": sha40Schema }).strict()

export const eventDataRunTakenOverSchema = z.object({ "reason": reasonSchema, "previous_state": runStateSchema }).strict()

export const eventDataDiagHookSchema = z.object({ "phase": hookPhaseSchema, "keys": z.array(z.string().max(100)).max(50) }).strict()

export const eventSchema = z.union([z.object({ "schema": z.literal("sak.event/1"), "event_id": ulidSchema, "type": z.literal("run.started"), "ts": timestampSchema, "project": projectKeySchema, "run_id": runIdSchema, "spec": specDirSchema.optional(), "origin": originSchema.optional(), "data": eventDataRunStartedSchema }).strict(), z.object({ "schema": z.literal("sak.event/1"), "event_id": ulidSchema, "type": z.literal("round.started"), "ts": timestampSchema, "project": projectKeySchema, "run_id": runIdSchema, "spec": specDirSchema.optional(), "origin": originSchema.optional(), "data": eventDataRoundStartedSchema }).strict(), z.object({ "schema": z.literal("sak.event/1"), "event_id": ulidSchema, "type": z.literal("station.started"), "ts": timestampSchema, "project": projectKeySchema, "run_id": runIdSchema, "spec": specDirSchema.optional(), "origin": originSchema.optional(), "data": eventDataStationStartedSchema }).strict(), z.object({ "schema": z.literal("sak.event/1"), "event_id": ulidSchema, "type": z.literal("station.finished"), "ts": timestampSchema, "project": projectKeySchema, "run_id": runIdSchema, "spec": specDirSchema.optional(), "origin": originSchema.optional(), "data": eventDataStationFinishedSchema }).strict(), z.object({ "schema": z.literal("sak.event/1"), "event_id": ulidSchema, "type": z.literal("verdict.recorded"), "ts": timestampSchema, "project": projectKeySchema, "run_id": runIdSchema, "spec": specDirSchema.optional(), "origin": originSchema.optional(), "data": eventDataVerdictRecordedSchema }).strict(), z.object({ "schema": z.literal("sak.event/1"), "event_id": ulidSchema, "type": z.literal("run.escalated"), "ts": timestampSchema, "project": projectKeySchema, "run_id": runIdSchema, "spec": specDirSchema.optional(), "origin": originSchema.optional(), "data": eventDataRunEscalatedSchema }).strict(), z.object({ "schema": z.literal("sak.event/1"), "event_id": ulidSchema, "type": z.enum(["run.released","run.returned","run.paused","run.aborted"]), "ts": timestampSchema, "project": projectKeySchema, "run_id": runIdSchema, "spec": specDirSchema.optional(), "origin": originSchema.optional(), "data": eventDataReasonOptionalSchema }).strict(), z.object({ "schema": z.literal("sak.event/1"), "event_id": ulidSchema, "type": z.enum(["run.resumed","run.approved","run.reviewed"]), "ts": timestampSchema, "project": projectKeySchema, "run_id": runIdSchema, "spec": specDirSchema.optional(), "origin": originSchema.optional(), "data": eventDataEmptySchema }).strict(), z.object({ "schema": z.literal("sak.event/1"), "event_id": ulidSchema, "type": z.literal("run.merged"), "ts": timestampSchema, "project": projectKeySchema, "run_id": runIdSchema, "spec": specDirSchema.optional(), "origin": originSchema.optional(), "data": eventDataRunMergedSchema }).strict(), z.object({ "schema": z.literal("sak.event/1"), "event_id": ulidSchema, "type": z.literal("run.pushed"), "ts": timestampSchema, "project": projectKeySchema, "run_id": runIdSchema, "spec": specDirSchema.optional(), "origin": originSchema.optional(), "data": eventDataRunPushedSchema }).strict(), z.object({ "schema": z.literal("sak.event/1"), "event_id": ulidSchema, "type": z.literal("run.taken_over"), "ts": timestampSchema, "project": projectKeySchema, "run_id": runIdSchema, "spec": specDirSchema.optional(), "origin": originSchema.optional(), "data": eventDataRunTakenOverSchema }).strict(), z.object({ "schema": z.literal("sak.event/1"), "event_id": ulidSchema, "type": z.literal("diag.hook"), "ts": timestampSchema, "project": projectKeySchema, "run_id": runIdSchema.optional(), "spec": specDirSchema.optional(), "origin": originSchema.optional(), "data": eventDataDiagHookSchema }).strict()])

export const boardSpecSchema = z.union([z.object({ "number": specNumberSchema, "dir": specDirSchema, "title": titleSchema, "descoped": z.literal(false), "blocked": z.boolean(), "waiting": z.union([z.enum(["approval","clarification"]), z.null()]), "tasks": z.object({ "done": countSchema, "open": countSchema, "partial": countSchema.optional() }).strict(), "started_at": timestampSchema.optional(), "finished_at": timestampSchema.optional(), "updated_at": timestampSchema.optional(), "lead_time_days": z.number().gte(0).optional(), "stage": z.union([stageSchema, z.null()]) }).strict(), z.object({ "number": specNumberSchema, "dir": specDirSchema, "title": titleSchema, "descoped": z.literal(true), "blocked": z.boolean(), "waiting": z.union([z.enum(["approval","clarification"]), z.null()]), "tasks": z.object({ "done": countSchema, "open": countSchema, "partial": countSchema.optional() }).strict(), "started_at": timestampSchema.optional(), "finished_at": timestampSchema.optional(), "updated_at": timestampSchema.optional(), "lead_time_days": z.number().gte(0).optional(), "stage": z.null() }).strict()])

export const boardAttentionSchema = z.object({ "kind": attentionKindSchema, "spec": specDirSchema.optional(), "reason": reasonSchema, "source": nameSchema }).strict()

export const boardStationSchema = z.object({ "round": roundSchema, "role": roleSchema, "agent": nameSchema, "model": nameSchema.optional(), "state": stationStateSchema, "started_at": timestampSchema, "duration_s": z.number().gte(0).optional(), "verdict": verdictSchema.optional(), "must_count": countSchema.optional(), "may_count": countSchema.optional() }).strict()

export const boardEscalationSchema = z.object({ "ts": timestampSchema, "round": roundSchema, "gate": gateSchema.optional(), "reason": reasonSchema, "open": z.boolean() }).strict()

export const boardRunSchema = z.object({ "run_id": runIdSchema, "spec": specDirSchema, "kind": runKindSchema, "state": runStateSchema, "round": roundSchema, "max_rounds": roundSchema, "active": z.boolean(), "started_at": timestampSchema, "updated_at": timestampSchema, "last_event_at": timestampSchema, "idle": z.boolean(), "stale": z.boolean(), "pushed": z.boolean().describe("Gesetzt (true), wenn ein run.pushed-Event zum Lauf vorliegt (Spec 012).").optional(), "origin": originSchema.optional(), "stations": z.array(boardStationSchema), "escalations": z.array(boardEscalationSchema) }).strict()

export const boardMarkerSchema = z.object({ "kind": markerKindSchema, "specs": z.array(specNumberSchema), "ts": timestampSchema, "commit": sha40Schema }).strict()

export const boardTickerEntrySchema = z.object({ "ts": timestampSchema, "spec": specDirSchema.optional(), "kind": tickerKindSchema, "text": titleSchema.optional(), "commit": z.string().regex(new RegExp("^[0-9a-f]{7,40}$")).optional() }).strict()

export const boardSchema = z.object({ "schema": z.literal("sak.board/1"), "generated_at": timestampSchema, "source": boardSourceSchema, "kit_version": nameSchema, "project": z.object({ "key": projectKeySchema, "name": nameSchema, "base_branch": nameSchema }).strict(), "metrics": z.object({ "in_progress": countSchema, "done": countSchema, "blocked": countSchema, "waiting": countSchema, "mean_lead_time_days": z.union([z.number().gte(0), z.null()]) }).strict(), "specs": z.array(boardSpecSchema), "attention": z.array(boardAttentionSchema), "runs": z.array(boardRunSchema).max(20), "markers": z.array(boardMarkerSchema), "ticker": z.array(boardTickerEntrySchema).max(30), "notes": z.array(z.string().min(1).max(300)).max(20) }).strict()

export const ingestRequestSchema = z.object({ "schema": z.literal("sak.ingest/1"), "project": projectKeySchema, "sent_at": timestampSchema, "events": z.array(eventSchema).max(500), "board": boardSchema.optional() }).strict()

export const ingestResultSchema = z.object({ "schema": z.literal("sak.ingest_result/1"), "accepted": countSchema, "duplicates": countSchema, "rejected": z.array(z.object({ "event_id": z.string().max(100).optional(), "error": reasonSchema }).strict()), "board_accepted": z.boolean() }).strict()

export const ingestSchema = z.union([ingestRequestSchema, ingestResultSchema])

export const configNonEmptyStringSchema = z.string().min(1).max(500)

export const configStringListSchema = z.array(configNonEmptyStringSchema)

export const configRoleConfigSchema = z.object({ "enabled": z.boolean().optional(), "agent": z.string().regex(new RegExp("^[A-Za-z0-9][A-Za-z0-9_-]*$")).describe("Dateiname unter .claude/agents/ ohne .md.").optional(), "model": configNonEmptyStringSchema.optional(), "effort": z.union([z.literal("low"), z.literal("medium"), z.literal("high")]).optional() }).strict()

export const configIntegratorConfigSchema = z.object({ "enabled": z.literal(false).optional(), "agent": z.string().regex(new RegExp("^[A-Za-z0-9][A-Za-z0-9_-]*$")).describe("Dateiname unter .claude/agents/ ohne .md.").optional(), "model": configNonEmptyStringSchema.optional(), "effort": z.union([z.literal("low"), z.literal("medium"), z.literal("high")]).optional() }).strict().describe("Der Integrator ist in v1 nicht aktivierbar (Spec 004 FR-002).")

export const configSchema = z.object({ "schema": z.literal("sak.config/1"), "project": z.object({ "key": projectKeySchema, "name": nameSchema, "base_branch": configNonEmptyStringSchema.optional() }).strict(), "locale": z.literal("de").optional(), "pipeline": z.object({ "max_rounds": z.number().int().gte(1).lte(5).optional(), "idle_minutes": z.number().int().gte(1).optional(), "stale_hours": z.number().int().gte(1).optional(), "branch_pattern": configNonEmptyStringSchema.optional(), "roles": z.object({ "builder": configRoleConfigSchema.optional(), "code_review": configRoleConfigSchema.optional(), "ui_review": configRoleConfigSchema.optional(), "security_review": configRoleConfigSchema.optional(), "docs": configRoleConfigSchema.optional(), "integrator": configIntegratorConfigSchema.optional() }).strict().optional() }).strict().optional(), "stages": z.object({ "deployed": z.boolean().optional(), "verified": z.boolean().optional() }).strict().optional(), "commands": z.object({ "test_fast": configStringListSchema.optional(), "test_full": configStringListSchema.optional(), "lint": configStringListSchema.optional(), "environment_failures": configStringListSchema.optional(), "prepare": configStringListSchema.optional() }).strict().optional(), "ui": z.object({ "command": configNonEmptyStringSchema, "base_url": z.string().regex(new RegExp("^https?://[^ ]+$")), "paths": configStringListSchema.optional(), "viewports": z.record(z.array(z.number().int().gte(1)).min(2).max(2)).optional(), "checks": configStringListSchema.optional(), "regression_tests": configStringListSchema.optional() }).strict().optional(), "guard": z.object({ "protected_paths": configStringListSchema.optional(), "clean_ignore": configStringListSchema.optional() }).strict().optional(), "escalation": z.object({ "paths": configStringListSchema.optional(), "topics": configStringListSchema.optional() }).strict().optional(), "review": z.object({ "rules": configStringListSchema.optional() }).strict().optional(), "orchestrator_only": configStringListSchema.optional(), "deploy": z.object({ "command": z.union([configNonEmptyStringSchema, z.null()]).optional() }).strict().optional(), "dashboard": z.object({ "url": z.union([z.string().regex(new RegExp("^https?://[^ ]+$")), z.null()]).optional(), "token_env": z.string().regex(new RegExp("^[A-Z_][A-Z0-9_]*$")).optional(), "push": z.union([z.literal("auto"), z.literal("manual"), z.literal("off")]).optional(), "auth": z.union([z.literal("key"), z.literal("proxy")]).optional(), "share_commit_subjects": z.boolean().optional() }).strict().optional(), "plugins": z.array(z.object({ "name": z.literal("legacy-status"), "options": z.record(z.any()).optional() }).strict()).max(10).describe("Plugins nach Name (Spec 010). Standard: leer.").optional(), "autonomy": z.object({ "push": z.union([z.literal("manual"), z.literal("after_merge")]).optional(), "deploy": z.union([z.literal("after_approval"), z.literal("never")]).optional(), "remote": configNonEmptyStringSchema.optional() }).strict().describe("Autonomie-Stufen (Spec 012). Defaults: push manual, deploy after_approval, remote origin.").optional() }).strict()

export const lockVersionSchema = z.string().regex(new RegExp("^[0-9]+[.][0-9]+[.][0-9]+(?:[-+][0-9A-Za-z.-]+)?$"))

export const lockSha256Schema = z.string().regex(new RegExp("^[0-9a-f]{64}$"))

export const lockSchema = z.object({ "schema": z.literal("sak.lock/1"), "kit_version": lockVersionSchema, "installed_at": timestampSchema, "upgraded_at": z.union([timestampSchema, z.null()]), "files": z.record(lockSha256Schema).describe("Relativer POSIX-Pfad im Zielprojekt -> SHA-256."), "settings_fragment_hash": lockSha256Schema, "settings_allow": z.array(z.string().min(1).max(300)).max(200).describe("Seit Kit 0.2.0 (optional, rückwärtskompatibel): die permissions.allow-Einträge, die das Kit in .claude/settings.json eingetragen hat. Beim Upgrade ersetzt das Kit genau diese Einträge; fremde Einträge bleiben. Fehlt das Feld (Lock vor 0.2.0), gelten nur bekannte Kit-Muster als Kit-eigen.").optional() }).strict()

export type SakEvent = z.infer<typeof eventSchema>
export type Board = z.infer<typeof boardSchema>
export type IngestRequest = z.infer<typeof ingestRequestSchema>
export type IngestResult = z.infer<typeof ingestResultSchema>
export type IngestDocument = z.infer<typeof ingestSchema>
export type SakConfig = z.infer<typeof configSchema>
export type SakLock = z.infer<typeof lockSchema>

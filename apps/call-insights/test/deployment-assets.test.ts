import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { EventIngestionService } from "../src/application/event-ingestion-service.js";
import { SqliteStore } from "../src/storage/sqlite-store.js";
import { retainRuntime } from "../scripts/retain-runtime.js";
import {
  makeAnalysis,
  makeNormalizedReportEvent,
  makeQuality,
  tempDirectory,
} from "./fixtures.js";

const ROOT = join(import.meta.dirname, "..");
const readAsset = (path: string) =>
  readFileSync(join(ROOT, path), "utf8");

describe("Linux deployment assets", () => {
  it("uses separate hardened non-root API and mail services", () => {
    const api = readAsset("deploy/vapi-call-insights.service");
    const mail = readAsset("deploy/vapi-call-insights-mail.service");

    for (const unit of [api, mail]) {
      expect(unit).toMatch(/^Group=vapi-call-insights$/m);
      expect(unit).toMatch(/^NoNewPrivileges=true$/m);
      expect(unit).toMatch(/^PrivateTmp=true$/m);
      expect(unit).toMatch(/^ProtectSystem=strict$/m);
      expect(unit).toMatch(/^ProtectProc=invisible$/m);
      expect(unit).toMatch(/^Restart=on-failure$/m);
      expect(unit).toMatch(/^ReadWritePaths=\/var\/lib\/vapi-call-insights /m);
    }
    expect(api).toMatch(/^User=vapi-call-insights$/m);
    expect(mail).toMatch(/^User=vapi-call-insights-mail$/m);
    expect(api).toContain(
      "EnvironmentFile=/etc/vapi-call-insights/api.env",
    );
    expect(api).not.toContain("mail.env");
    expect(api).not.toMatch(/GMAIL|RECIPIENT/i);
    expect(mail).toContain(
      "EnvironmentFile=/etc/vapi-call-insights/mail.env",
    );
    expect(mail).not.toContain("api.env");
    expect(mail).not.toMatch(/VAPI_API|DEEPSEEK/i);
  });

  it("keeps environment templates free of secrets and routable addresses", () => {
    const api = readAsset("deploy/vapi-call-insights.env.example");
    const mail = readAsset("deploy/vapi-call-insights-mail.env.example");
    const recipients = readAsset("deploy/mail-recipients.example.json");
    const combined = `${api}\n${mail}\n${recipients}`;

    expect(api).toMatch(/^VAPI_API_KEY=$/m);
    expect(api).toMatch(/^DEEPSEEK_API_KEY=$/m);
    expect(api).toMatch(/^WEBHOOK_AUTH_TOKEN=$/m);
    expect(api).toMatch(/^INGEST_AUTH_TOKEN=$/m);
    expect(mail).toMatch(/^GMAIL_APP_PASSWORD=$/m);
    expect(mail).toMatch(/^MAIL_RECIPIENT_CONFIG_SHA256=$/m);
    expect(api).toMatch(
      /^PROFILES_DIRECTORY=\/etc\/vapi-call-insights\/profiles$/m,
    );
    expect(mail).toMatch(
      /^PROFILES_DIRECTORY=\/etc\/vapi-call-insights\/profiles$/m,
    );
    expect(recipients).toContain('"lucaplus"');
    expect(recipients).toContain('"inp-group"');
    expect(combined).not.toMatch(
      /(?:sk-|Bearer\s+)[A-Za-z0-9_-]{12,}|@(?:lucaplus|inpgroup)\./i,
    );
  });

  it("proxies only calls.yino.au to loopback with a five MiB limit", () => {
    const nginx = readAsset("deploy/calls.yino.au.nginx.conf");

    expect(nginx).toMatch(/server_name\s+calls\.yino\.au;/);
    expect(nginx).toMatch(/client_max_body_size\s+5m;/);
    expect(nginx).toMatch(
      /proxy_pass\s+http:\/\/127\.0\.0\.1:3210;/,
    );
    expect(nginx).not.toMatch(/proxy_pass\s+http:\/\/(?!127\.0\.0\.1)/);
    expect(nginx).toContain("location ~ ^/v1/(?:jobs|calls)/");
    expect(nginx).toMatch(/return\s+404;/);
    expect(nginx).toContain("allow 127.0.0.1;");
    expect(nginx).toContain("allow 104.16.0.0/13;");
    expect(nginx).toContain("deny all;");
  });

  it("uses online SQLite backup, read-only verification, and private modes", () => {
    const backup = readAsset("scripts/backup-runtime.sh");

    expect(backup).toContain("umask 077");
    expect(backup).toMatch(/sqlite3[\s\S]*\.backup/);
    expect(backup).toMatch(/sqlite3\s+-readonly[\s\S]*quick_check/);
    expect(backup).toMatch(/chmod 700/);
    expect(backup).toMatch(/chmod 600/);
    expect(backup).toContain(".partial");
    expect(backup).toMatch(/\bmv\s+/);
    expect(backup).not.toMatch(/\bcp\s+.*\.sqlite/);
  });

  it("deploys versioned releases without embedded credentials", () => {
    const deployer = readAsset("deploy-calls-yino.py");

    expect(deployer).toContain("--dry-run");
    expect(deployer).toContain("npm ci");
    expect(deployer).toContain("systemctl");
    expect(deployer).toContain("/opt/vapi-call-insights/releases");
    expect(deployer).toContain("SOURCE_PATHS");
    expect(deployer).toContain("tar_info.mode");
    expect(deployer.indexOf("mail_pre_activation")).toBeLessThan(
      deployer.indexOf("npm ci"),
    );
    expect(deployer).toContain("systemctl restart vapi-call-insights.service");
    expect(deployer).toContain("http://127.0.0.1:3210/livez");
    expect(deployer).toContain("api_healthy=false");
    expect(deployer).toContain(
      "if test -L {REMOTE_ROOT}/current",
    );
    expect(deployer).toContain(
      'test -d \\"$previous_release\\"',
    );
    expect(deployer).toMatch(
      /systemctl is-active --quiet "\s*"vapi-call-insights-mail\.service/,
    );
    expect(deployer).toContain("http://127.0.0.1:3210/health");
    expect(deployer).not.toMatch(/8\.215\.80\.82|Zynisgood|api[_ -]?key\s*=/i);
  });

  it("installs daily verified backups and retention timers", () => {
    const backupTimer = readAsset(
      "deploy/vapi-call-insights-backup.timer",
    );
    const retentionTimer = readAsset(
      "deploy/vapi-call-insights-retention.timer",
    );
    const backupService = readAsset(
      "deploy/vapi-call-insights-backup.service",
    );
    const retentionService = readAsset(
      "deploy/vapi-call-insights-retention.service",
    );

    expect(backupTimer).toMatch(/^OnCalendar=daily$/m);
    expect(retentionTimer).toMatch(/^OnCalendar=daily$/m);
    expect(backupService).toContain("backup-runtime.sh");
    expect(retentionService).toContain("runtime:retain");
    expect(retentionService).toMatch(
      /^Requires=vapi-call-insights-backup\.service$/m,
    );
    for (const unit of [backupService, retentionService]) {
      expect(unit).toMatch(/^NoNewPrivileges=true$/m);
      expect(unit).toMatch(/^PrivateTmp=true$/m);
    }
  });
});

describe("runtime retention", () => {
  it("removes ninety-day PII and artifacts while retaining scrubbed outbox audit", () => {
    const root = tempDirectory();
    const databasePath = join(root.path, "runtime.sqlite");
    const artifactDirectory = join(root.path, "artifacts");
    const callId = "call_retention_old";
    const store = new SqliteStore(databasePath);
    const accepted = new EventIngestionService(store).ingest(
      makeNormalizedReportEvent("lucaplus", callId),
    );
    store.saveAnalysis(
      "lucaplus",
      callId,
      "mock",
      makeAnalysis({ customerName: "Private Customer" }),
      makeQuality({ summary: "Private quality summary" }),
      "2026-08-13T02:00:00.000Z",
    );
    const mail = store.enqueueMail({
      profile: "lucaplus",
      callId,
      kind: "customer",
      subject: "Private Customer report",
      htmlPath: join(
        artifactDirectory,
        "lucaplus",
        callId,
        "customer-report.html",
      ),
      recipientRoles: ["customer-report-primary"],
      messageId: "<retained-audit@calls.yino.au>",
      status: "suppressed",
      nextAttemptAt: null,
    });
    expect(accepted.jobId).not.toBeNull();
    expect(store.claimNextJob()?.jobId).toBe(accepted.jobId);
    store.succeedJob(accepted.jobId!);
    const callArtifacts = join(artifactDirectory, "lucaplus", callId);
    mkdirSync(callArtifacts, { recursive: true });
    writeFileSync(
      join(callArtifacts, "customer-report.html"),
      "Private Customer private@example.test",
      "utf8",
    );
    store.close();

    try {
      expect(retainRuntime({
        databasePath,
        artifactDirectory,
        now: new Date("2026-11-12T00:00:00.000Z"),
      })).toEqual({
        callsRemoved: 1,
        artifactDirectoriesRemoved: 1,
        outboxRowsScrubbed: 1,
      });

      const inspection = new SqliteStore(databasePath);
      try {
        expect(inspection.getCall("lucaplus", callId)).toBeNull();
        expect(inspection.getAnalysis("lucaplus", callId)).toBeNull();
        expect(inspection.countEvents()).toBe(0);
        expect(inspection.countJobs()).toBe(0);
        expect(inspection.getMail(mail.outboxId)).toMatchObject({
          profile: "lucaplus",
          callId,
          kind: "customer",
          subject: "",
          htmlPath: "",
          recipientRoles: [],
          status: "suppressed",
          lastError: null,
          providerMessageId: null,
        });
      } finally {
        inspection.close();
      }
      expect(existsSync(callArtifacts)).toBe(false);
    } finally {
      root.close();
    }
  });

  it("does not remove a call while its analysis job is active", () => {
    const root = tempDirectory();
    const databasePath = join(root.path, "runtime.sqlite");
    const artifactDirectory = join(root.path, "artifacts");
    const callId = "call_retention_active";
    const callArtifacts = join(artifactDirectory, "lucaplus", callId);
    const store = new SqliteStore(databasePath);
    new EventIngestionService(store).ingest(
      makeNormalizedReportEvent("lucaplus", callId),
    );
    mkdirSync(callArtifacts, { recursive: true });
    writeFileSync(
      join(callArtifacts, "customer-report.html"),
      "still active",
      "utf8",
    );
    store.close();

    try {
      expect(retainRuntime({
        databasePath,
        artifactDirectory,
        now: new Date("2026-11-12T00:00:00.000Z"),
      })).toEqual({
        callsRemoved: 0,
        artifactDirectoriesRemoved: 0,
        outboxRowsScrubbed: 0,
      });
      const inspection = new SqliteStore(databasePath);
      try {
        expect(inspection.getCall("lucaplus", callId)).not.toBeNull();
      } finally {
        inspection.close();
      }
      expect(existsSync(callArtifacts)).toBe(true);
    } finally {
      root.close();
    }
  });

  it("drains more than one bounded retention batch", () => {
    const root = tempDirectory();
    const databasePath = join(root.path, "runtime.sqlite");
    const store = new SqliteStore(databasePath);
    try {
      for (let index = 0; index < 26; index += 1) {
        const accepted = new EventIngestionService(store).ingest(
          makeNormalizedReportEvent(
            "lucaplus",
            `call_retention_batch_${index}`,
          ),
        );
        expect(store.claimNextJob()?.jobId).toBe(accepted.jobId);
        store.succeedJob(accepted.jobId!);
      }
    } finally {
      store.close();
    }

    try {
      expect(retainRuntime({
        databasePath,
        artifactDirectory: join(root.path, "artifacts"),
        now: new Date("2027-01-01T00:00:00.000Z"),
      })).toEqual({
        callsRemoved: 26,
        artifactDirectoriesRemoved: 0,
        outboxRowsScrubbed: 0,
      });
    } finally {
      root.close();
    }
  });
});

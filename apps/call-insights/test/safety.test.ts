import { spawnSync, type SpawnSyncReturns } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import * as ts from "typescript/unstable/ast";
import { API as TypeScriptApi } from "typescript/unstable/sync";
import { describe, expect, it, vi } from "vitest";
import packageJson from "../package.json" with { type: "json" };

const PACKAGE_ROOT = fileURLToPath(new URL("../", import.meta.url));
const FIXTURE_PATH = fileURLToPath(
  new URL("../fixtures/vapi/end-of-call.json", import.meta.url),
);
const PRODUCTION_SOURCE_PATH = fileURLToPath(
  new URL("../src", import.meta.url),
);
const EMAIL_TOOLS_PATH = fileURLToPath(
  new URL("../tools", import.meta.url),
);
const EMAIL_ENTRYPOINT_PATH = fileURLToPath(
  new URL("../tools/send-test-email-entrypoint.ts", import.meta.url),
);
const EMAIL_WRAPPER_PATH = fileURLToPath(
  new URL("../scripts/send-test-email.ps1", import.meta.url),
);
const TRIAL_EMAIL_ENTRYPOINT_PATH = fileURLToPath(
  new URL("../tools/send-trial-email-entrypoint.ts", import.meta.url),
);
const SMTP_TRANSPORT_PATH = fileURLToPath(
  new URL("../tools/mail/smtp-transport.ts", import.meta.url),
);
const TRIAL_EMAIL_WRAPPER_PATH = fileURLToPath(
  new URL("../scripts/send-trial-email.ps1", import.meta.url),
);
const TSCONFIG_PATH = fileURLToPath(new URL("../tsconfig.json", import.meta.url));
const POWERSHELL = process.platform === "win32" ? "powershell.exe" : "pwsh";

interface ModuleReference {
  filePath: string;
  kind:
    | "dynamic-import"
    | "export"
    | "import"
    | "import-equals"
    | "import-type";
  specifier: string | null;
  node: ts.Node;
  sourceFile: ts.SourceFile;
}

interface WrapperScenario {
  confirmation?: string;
  mode:
    | "cancel"
    | "launcher-throw"
    | "malformed-zero"
    | "missing-deepseek"
    | "missing-vapi-file"
    | "nonzero"
    | "success";
}

interface WrapperScenarioResult {
  capture: string | null;
  foreignCwd: string;
  result: SpawnSyncReturns<string>;
  securePrompted: boolean;
  ui: string;
}

function typeScriptFiles(rootPath: string): string[] {
  return readdirSync(rootPath, { withFileTypes: true })
    .flatMap((entry): string[] => {
      const path = join(rootPath, entry.name);
      if (entry.isDirectory()) {
        return typeScriptFiles(path);
      }
      return entry.isFile() && entry.name.endsWith(".ts")
        ? [path]
        : [];
    })
    .sort();
}

function stringLiteralValue(node: ts.Node | undefined): string | null {
  return node !== undefined &&
    (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node))
    ? node.text
    : null;
}

function moduleReferencesFromAst(
  filePath: string,
  sourceFile: ts.SourceFile,
): ModuleReference[] {
  const references: ModuleReference[] = [];
  const add = (
    kind: ModuleReference["kind"],
    node: ts.Node,
    specifier: string | null,
  ): void => {
    references.push({ filePath, kind, specifier, node, sourceFile });
  };

  const visit = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node)) {
      add("import", node, stringLiteralValue(node.moduleSpecifier));
    } else if (ts.isExportDeclaration(node) && node.moduleSpecifier) {
      add("export", node, stringLiteralValue(node.moduleSpecifier));
    } else if (
      ts.isImportEqualsDeclaration(node) &&
      ts.isExternalModuleReference(node.moduleReference)
    ) {
      add(
        "import-equals",
        node,
        stringLiteralValue(node.moduleReference.expression),
      );
    } else if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword
    ) {
      add("dynamic-import", node, stringLiteralValue(node.arguments[0]));
    } else if (ts.isImportTypeNode(node)) {
      const literal = ts.isLiteralTypeNode(node.argument)
        ? stringLiteralValue(node.argument.literal)
        : null;
      add("import-type", node, literal);
    }
    ts.visitEachChild(node, (child) => {
      visit(child);
      return child;
    });
  };
  visit(sourceFile);
  return references;
}

function moduleReferencesFromFiles(filePaths: readonly string[]): ModuleReference[] {
  const api = new TypeScriptApi();
  const snapshot = api.updateSnapshot({ openFiles: [...filePaths] });
  try {
    return filePaths.flatMap((filePath) => {
      const project = snapshot.getDefaultProjectForFile(filePath);
      const sourceFile = project?.program.getSourceFile(filePath);
      if (!sourceFile) {
        throw new Error(`typescript_ast_missing:${filePath}`);
      }
      return moduleReferencesFromAst(filePath, sourceFile);
    });
  } finally {
    snapshot.dispose();
    api.close();
  }
}

function moduleReferencesFromSource(sourceText: string): ModuleReference[] {
  const rootPath = mkdtempSync(join(tmpdir(), "email-ast-test-"));
  const filePath = join(rootPath, "entrypoint.ts");
  writeFileSync(filePath, sourceText, "utf8");
  try {
    return moduleReferencesFromFiles([filePath]);
  } finally {
    rmSync(rootPath, { recursive: true, force: true });
  }
}

function isNodemailerSpecifier(specifier: string | null): boolean {
  return (
    specifier !== null &&
    (specifier.toLowerCase() === "nodemailer" ||
      specifier.toLowerCase().startsWith("nodemailer/"))
  );
}

function isTestMailToolSpecifier(specifier: string | null): boolean {
  if (specifier === null) {
    return false;
  }
  const normalized = specifier.replaceAll("\\", "/").toLowerCase();
  return /(?:^|\/)tools\/(?:send-test-email|send-trial-email|pull-lucaplus-call)(?:-entrypoint)?(?:\.[a-z0-9]+)?$/.test(
    normalized,
  );
}

function toolImportPolicyViolations(
  references: readonly ModuleReference[],
): string[] {
  const dynamicImports = references.filter(
    (reference) => reference.kind === "dynamic-import",
  );
  const violations: string[] = [];
  if (dynamicImports.length !== 1) {
    violations.push(`dynamic-import-count:${dynamicImports.length}`);
  }
  for (const reference of dynamicImports) {
    if (reference.specifier !== "nodemailer") {
      violations.push(`dynamic-import-specifier:${reference.specifier}`);
    }
  }
  for (const reference of references) {
    if (
      reference.kind !== "dynamic-import" &&
      isNodemailerSpecifier(reference.specifier)
    ) {
      violations.push(`${reference.kind}:${reference.specifier}`);
    }
  }
  return violations;
}

function ancestor<T extends ts.Node>(
  node: ts.Node,
  predicate: (candidate: ts.Node) => candidate is T,
): T | undefined {
  let current = node.parent;
  while (current) {
    if (predicate(current)) {
      return current;
    }
    current = current.parent;
  }
  return undefined;
}

function isNodeWithin(node: ts.Node, possibleAncestor: ts.Node): boolean {
  let current: ts.Node | undefined = node;
  while (current) {
    if (current === possibleAncestor) {
      return true;
    }
    current = current.parent;
  }
  return false;
}

function isEntrypointGuard(node: ts.IfStatement): boolean {
  return (
    ts.isCallExpression(node.expression) &&
    ts.isIdentifier(node.expression.expression) &&
    node.expression.expression.text === "isEntrypoint" &&
    node.expression.arguments.length === 0
  );
}

function entrypointGuardAncestor(node: ts.Node): ts.IfStatement | undefined {
  let current = node.parent;
  while (current) {
    if (ts.isIfStatement(current) && isEntrypointGuard(current)) {
      return current;
    }
    current = current.parent;
  }
  return undefined;
}

function directEnvironmentAssertion(
  statement: ts.Statement | undefined,
): boolean {
  if (!statement || !ts.isExpressionStatement(statement)) {
    return false;
  }
  const expression = statement.expression;
  if (
    !ts.isCallExpression(expression) ||
    !ts.isIdentifier(expression.expression) ||
    (expression.expression.text !== "assertEmailTestEnvironment" &&
      expression.expression.text !== "assertTrialEmailEnvironment") ||
    expression.arguments.length !== 1
  ) {
    return false;
  }
  const argument = expression.arguments[0];
  return (
    argument !== undefined &&
    ts.isPropertyAccessExpression(argument) &&
    ts.isIdentifier(argument.expression) &&
    argument.expression.text === "process" &&
    argument.name.text === "env"
  );
}

function hasTerminatingValidationStep(
  statement: ts.Statement | undefined,
): boolean {
  if (directEnvironmentAssertion(statement)) {
    return true;
  }
  if (!statement || !ts.isTryStatement(statement)) {
    return false;
  }
  const catchStatements = statement.catchClause?.block.statements;
  return (
    directEnvironmentAssertion(statement.tryBlock.statements[0]) &&
    catchStatements !== undefined &&
    catchStatements.length > 0 &&
    ts.isReturnStatement(catchStatements[catchStatements.length - 1]!)
  );
}

function containingDirectStatement(
  block: ts.Block,
  node: ts.Node,
): ts.Statement | undefined {
  return block.statements.find((statement) => isNodeWithin(node, statement));
}

function immediateArrowInvocation(
  arrow: ts.ArrowFunction,
): ts.CallExpression | undefined {
  let expression: ts.Expression = arrow;
  let parent = arrow.parent;
  while (parent && ts.isParenthesizedExpression(parent)) {
    expression = parent;
    parent = parent.parent;
  }
  return parent &&
    ts.isCallExpression(parent) &&
    parent.expression === expression
    ? parent
    : undefined;
}

function hasConditionalExecutionBoundary(
  node: ts.Node,
  stopAt: ts.Node,
): boolean {
  let current = node.parent;
  while (current && current !== stopAt) {
    if (
      ts.isArrowFunction(current) ||
      ts.isFunctionExpression(current) ||
      ts.isFunctionDeclaration(current) ||
      ts.isIfStatement(current) ||
      ts.isConditionalExpression(current) ||
      ts.isSwitchStatement(current) ||
      ts.isCaseClause(current) ||
      ts.isDefaultClause(current) ||
      ts.isForStatement(current) ||
      ts.isForInStatement(current) ||
      ts.isForOfStatement(current) ||
      ts.isWhileStatement(current) ||
      ts.isDoStatement(current) ||
      ts.isCatchClause(current) ||
      (ts.isBlock(current) &&
        ts.isTryStatement(current.parent) &&
        current.parent.finallyBlock === current)
    ) {
      return true;
    }
    current = current.parent;
  }
  return current !== stopAt;
}

function entrypointExecutionPolicyViolations(
  nodemailerLoad: ModuleReference,
): string[] {
  const violations: string[] = [];
  const guard = entrypointGuardAncestor(nodemailerLoad.node);
  if (!guard || !ts.isSourceFile(guard.parent)) {
    violations.push("missing-top-level-entrypoint-guard");
    return violations;
  }
  if (!isNodeWithin(nodemailerLoad.node, guard.thenStatement)) {
    violations.push("import-outside-guard-then");
  }

  const guardedFunction = ancestor(nodemailerLoad.node, ts.isArrowFunction);
  if (!guardedFunction || !ts.isBlock(guardedFunction.body)) {
    violations.push("missing-guarded-async-body");
    return violations;
  }
  const invocation = immediateArrowInvocation(guardedFunction);
  if (
    !invocation ||
    !isNodeWithin(invocation, guard.thenStatement) ||
    hasConditionalExecutionBoundary(invocation, guard.thenStatement)
  ) {
    violations.push("guarded-body-not-directly-invoked");
  }

  const body = guardedFunction.body;
  const validationStep = body.statements[0];
  if (!hasTerminatingValidationStep(validationStep)) {
    violations.push("validation-not-direct-unavoidable-first-step");
  }

  const importStep = containingDirectStatement(body, nodemailerLoad.node);
  const importStepIndex =
    importStep === undefined ? -1 : body.statements.indexOf(importStep);
  if (importStepIndex <= 0) {
    violations.push("import-not-after-validation-step");
  }
  if (
    importStep === undefined ||
    hasConditionalExecutionBoundary(nodemailerLoad.node, importStep)
  ) {
    violations.push("import-not-on-direct-sequential-path");
  }
  return violations;
}

function emailTestEnvironment(
  extra: NodeJS.ProcessEnv = {},
): NodeJS.ProcessEnv {
  const environment = {
    ...process.env,
    ...extra,
  };
  delete environment.REAL_EMAIL_TEST_CONFIRM;
  delete environment.GMAIL_TEST_APP_PASSWORD;
  return environment;
}

function readPowerShellText(path: string): string {
  const contents = readFileSync(path);
  return contents[0] === 0xff && contents[1] === 0xfe
    ? contents.subarray(2).toString("utf16le")
    : contents.toString("utf8");
}

function runWrapperScenario(
  scenario: WrapperScenario,
): WrapperScenarioResult {
  const rootPath = mkdtempSync(join(tmpdir(), "email-wrapper-test-"));
  const fakeBinPath = join(rootPath, "fake-bin");
  const foreignCwd = join(rootPath, "foreign-cwd");
  const harnessPath = join(rootPath, "wrapper-harness.ps1");
  const fakeNpmPath = join(fakeBinPath, "npm.cmd");
  const capturePath = join(rootPath, "npm-capture.txt");
  const securePromptPath = join(rootPath, "secure-prompt.txt");
  const uiPath = join(rootPath, "ui.txt");
  mkdirSync(fakeBinPath);
  mkdirSync(foreignCwd);

  writeFileSync(
    fakeNpmPath,
    [
      "@echo off",
      '> "%WRAPPER_CAPTURE_PATH%" (',
      "  echo cwd=%CD%",
      "  echo arg1=%~1",
      "  echo arg2=%~2",
      "  echo arg3=%~3",
      "  echo arg4=%~4",
      "  echo arg5=%~5",
      "  echo confirmation=%REAL_EMAIL_TEST_CONFIRM%",
      "  if defined GMAIL_TEST_APP_PASSWORD echo credential=present",
      ")",
      'if /I "%WRAPPER_FAKE_MODE%"=="nonzero" (',
      "  echo sensitive-child-stdout",
      "  1>&2 echo sensitive-child-stderr",
      "  exit /b 7",
      ")",
      'if /I "%WRAPPER_FAKE_MODE%"=="malformed-zero" (',
      "  echo sensitive-malformed-child-output",
      "  exit /b 0",
      ")",
      'echo {"status":"sent"}',
      "exit /b 0",
    ].join("\r\n"),
    "utf8",
  );
  writeFileSync(
    harnessPath,
    [
      '$ErrorActionPreference = "Stop"',
      "function Read-Host {",
      "  param([string]$Prompt, [switch]$AsSecureString)",
      "  if ($AsSecureString) {",
      '    Set-Content -LiteralPath $env:SECURE_PROMPT_PATH -Value "called"',
      '    return ConvertTo-SecureString "synthetic-test-secret" -AsPlainText -Force',
      "  }",
      "  return $env:WRAPPER_CONFIRMATION",
      "}",
      'if ($env:WRAPPER_FAKE_MODE -eq "launcher-throw") {',
      "  function npm { throw 'sensitive-launcher-exception' }",
      "}",
      "Set-Location -LiteralPath $env:FOREIGN_CWD",
      "& $env:WRAPPER_UNDER_TEST 6> $env:WRAPPER_UI_PATH",
      "$wrapperExitCode = $LASTEXITCODE",
      'if (Test-Path Env:REAL_EMAIL_TEST_CONFIRM) { throw "confirmation leaked" }',
      'if (Test-Path Env:GMAIL_TEST_APP_PASSWORD) { throw "credential leaked" }',
      "exit $wrapperExitCode",
    ].join("\r\n"),
    "utf8",
  );

  const environment = emailTestEnvironment({
    FOREIGN_CWD: foreignCwd,
    SECURE_PROMPT_PATH: securePromptPath,
    WRAPPER_CAPTURE_PATH: capturePath,
    WRAPPER_CONFIRMATION:
      scenario.confirmation ??
      (scenario.mode === "cancel" ? "wrong" : "SEND 867542127@qq.com"),
    WRAPPER_FAKE_MODE: scenario.mode,
    WRAPPER_UI_PATH: uiPath,
    WRAPPER_UNDER_TEST: EMAIL_WRAPPER_PATH,
  });
  const pathKey =
    Object.keys(environment).find((key) => key.toLowerCase() === "path") ??
    "Path";
  environment[pathKey] = `${fakeBinPath}${delimiter}${environment[pathKey] ?? ""}`;

  try {
    const result = spawnSync(
      POWERSHELL,
      ["-NoLogo", "-NoProfile", "-NonInteractive", "-File", harnessPath],
      {
        cwd: foreignCwd,
        encoding: "utf8",
        env: environment,
      },
    );
    return {
      capture: existsSync(capturePath)
        ? readFileSync(capturePath, "utf8")
        : null,
      foreignCwd,
      result,
      securePrompted: existsSync(securePromptPath),
      ui: existsSync(uiPath) ? readPowerShellText(uiPath) : "",
    };
  } finally {
    rmSync(rootPath, { recursive: true, force: true });
  }
}

function runTrialWrapperScenario(
  scenario: WrapperScenario,
): WrapperScenarioResult {
  const rootPath = mkdtempSync(join(tmpdir(), "trial-wrapper-test-"));
  const fakeBinPath = join(rootPath, "fake-bin");
  const foreignCwd = join(rootPath, "foreign-cwd");
  const harnessPath = join(rootPath, "wrapper-harness.ps1");
  const fakeNpmPath = join(fakeBinPath, "npm.cmd");
  const capturePath = join(rootPath, "npm-capture.txt");
  const securePromptPath = join(rootPath, "secure-prompt.txt");
  const uiPath = join(rootPath, "ui.txt");
  const vapiKeyPath = join(rootPath, "vapi-key.txt");
  const missingVapiKeyPath = join(rootPath, "missing-vapi-key.txt");
  const deepseekKeyPath = join(rootPath, "deepseek-key.txt");
  const missingDeepseekKeyPath = join(rootPath, "missing-deepseek-key.txt");
  mkdirSync(fakeBinPath);
  mkdirSync(foreignCwd);
  writeFileSync(vapiKeyPath, "vapi-test-key\n", "utf8");
  writeFileSync(deepseekKeyPath, "sk-test-deepseek-file\n", "utf8");

  writeFileSync(
    fakeNpmPath,
    [
      "@echo off",
      '> "%WRAPPER_CAPTURE_PATH%" (',
      "  echo cwd=%CD%",
      "  echo arg1=%~1",
      "  echo arg2=%~2",
      "  echo arg3=%~3",
      "  echo arg4=%~4",
      "  echo arg5=%~5",
      "  echo confirmation=%REAL_EMAIL_TEST_CONFIRM%",
      "  if defined GMAIL_TEST_APP_PASSWORD echo credential=present",
      "  if defined VAPI_API_KEY echo vapi=present",
      "  if defined DEEPSEEK_API_KEY echo deepseek=present",
      "  echo provider=%AI_PROVIDER%",
      ")",
      'if /I "%WRAPPER_FAKE_MODE%"=="nonzero" (',
      "  echo sensitive-child-stdout",
      "  1>&2 echo sensitive-child-stderr",
      "  exit /b 7",
      ")",
      'if /I "%WRAPPER_FAKE_MODE%"=="malformed-zero" (',
      "  echo sensitive-malformed-child-output",
      "  exit /b 0",
      ")",
      'echo {"status":"sent"}',
      "exit /b 0",
    ].join("\r\n"),
    "utf8",
  );
  writeFileSync(
    harnessPath,
    [
      '$ErrorActionPreference = "Stop"',
      "function Read-Host {",
      "  param([string]$Prompt, [switch]$AsSecureString)",
      "  if ($AsSecureString) {",
      '    Set-Content -LiteralPath $env:SECURE_PROMPT_PATH -Value "called"',
      '    return ConvertTo-SecureString "synthetic-test-secret" -AsPlainText -Force',
      "  }",
      "  return $env:WRAPPER_CONFIRMATION",
      "}",
      'if ($env:WRAPPER_FAKE_MODE -eq "launcher-throw") {',
      "  function npm { throw 'sensitive-launcher-exception' }",
      "}",
      "Set-Location -LiteralPath $env:FOREIGN_CWD",
      "$hadVapi = Test-Path Env:VAPI_API_KEY",
      "$hadDeepseek = Test-Path Env:DEEPSEEK_API_KEY",
      "$hadAi = Test-Path Env:AI_PROVIDER",
      "$previousAi = $env:AI_PROVIDER",
      "& $env:WRAPPER_UNDER_TEST 6> $env:WRAPPER_UI_PATH",
      "$wrapperExitCode = $LASTEXITCODE",
      'if (Test-Path Env:REAL_EMAIL_TEST_CONFIRM) { throw "confirmation leaked" }',
      'if (Test-Path Env:GMAIL_TEST_APP_PASSWORD) { throw "credential leaked" }',
      'if (-not $hadVapi -and (Test-Path Env:VAPI_API_KEY)) { throw "vapi leaked" }',
      'if (-not $hadDeepseek -and (Test-Path Env:DEEPSEEK_API_KEY)) { throw "deepseek leaked" }',
      'if ($hadAi) {',
      '  if ($env:AI_PROVIDER -cne $previousAi) { throw "ai provider mutated" }',
      "} else {",
      '  if (Test-Path Env:AI_PROVIDER) { throw "ai provider leaked" }',
      "}",
      "exit $wrapperExitCode",
    ].join("\r\n"),
    "utf8",
  );

  const environment = emailTestEnvironment({
    FOREIGN_CWD: foreignCwd,
    SECURE_PROMPT_PATH: securePromptPath,
    TRIAL_DEEPSEEK_KEY_FILE:
      scenario.mode === "missing-deepseek"
        ? missingDeepseekKeyPath
        : deepseekKeyPath,
    TRIAL_VAPI_KEY_FILE:
      scenario.mode === "missing-vapi-file" ? missingVapiKeyPath : vapiKeyPath,
    WRAPPER_CAPTURE_PATH: capturePath,
    WRAPPER_CONFIRMATION:
      scenario.confirmation ??
      (scenario.mode === "cancel" ? "wrong" : "SEND 867542127@qq.com"),
    WRAPPER_FAKE_MODE: scenario.mode,
    WRAPPER_UI_PATH: uiPath,
    WRAPPER_UNDER_TEST: TRIAL_EMAIL_WRAPPER_PATH,
  });
  delete environment.VAPI_API_KEY;
  delete environment.AI_PROVIDER;
  delete environment.DEEPSEEK_API_KEY;
  const pathKey =
    Object.keys(environment).find((key) => key.toLowerCase() === "path") ??
    "Path";
  environment[pathKey] = `${fakeBinPath}${delimiter}${environment[pathKey] ?? ""}`;

  try {
    const result = spawnSync(
      POWERSHELL,
      ["-NoLogo", "-NoProfile", "-NonInteractive", "-File", harnessPath],
      {
        cwd: foreignCwd,
        encoding: "utf8",
        env: environment,
      },
    );
    return {
      capture: existsSync(capturePath)
        ? readFileSync(capturePath, "utf8")
        : null,
      foreignCwd,
      result,
      securePrompted: existsSync(securePromptPath),
      ui: existsSync(uiPath) ? readPowerShellText(uiPath) : "",
    };
  } finally {
    rmSync(rootPath, { recursive: true, force: true });
  }
}

async function runCompleteMockPipeline(): Promise<void> {
  const rootPath = mkdtempSync(join(tmpdir(), "vapi-call-insights-safety-"));
  const databasePath = join(rootPath, "database", "safety.sqlite");
  const artifactRoot = join(rootPath, "artifacts");
  const args = [
    "--profile",
    "lucaplus",
    "--file",
    FIXTURE_PATH,
    "--wait",
    "--database",
    databasePath,
    "--artifacts",
    artifactRoot,
  ];
  const { createReplayRuntime, runReplay } = await import(
    "../src/cli/replay.js"
  );
  const runtime = createReplayRuntime(args, {});

  try {
    const result = await runReplay(args, runtime.dependencies);

    expect(result.status).toBe("succeeded");
    expect(result.files).toHaveLength(4);
    expect(result.files.every(existsSync)).toBe(true);
    expect(runtime.dependencies.store.getAnalysis("lucaplus", "call_demo_001")?.provider)
      .toBe("mock");

    const temporaryPrefix = `${resolve(rootPath)}${sep}`;
    expect(resolve(databasePath).startsWith(temporaryPrefix)).toBe(true);
    expect(resolve(artifactRoot).startsWith(temporaryPrefix)).toBe(true);
    expect(result.files.every((path) => resolve(path).startsWith(temporaryPrefix))).toBe(true);
  } finally {
    await runtime.close();
    rmSync(rootPath, { recursive: true, force: true });
  }
}

describe("safety policy", () => {
  it("contains only the approved runtime dependencies", () => {
    expect(Object.keys(packageJson.dependencies ?? {}).sort()).toEqual([
      "fastify",
      "nodemailer",
      "tsx",
      "zod",
    ]);
    expect(packageJson.devDependencies?.["@types/nodemailer"]).toBeDefined();
  });

  it("targets the dedicated email entrypoint from the package script", () => {
    expect(packageJson.scripts["test:email"]).toBe(
      "tsx tools/send-test-email-entrypoint.ts",
    );
    expect(packageJson.scripts["test:trial-email"]).toBe(
      "tsx tools/send-trial-email-entrypoint.ts",
    );
  });

  it("keeps every email tool inside the configured typecheck project", () => {
    const api = new TypeScriptApi();
    const snapshot = api.updateSnapshot({ openProjects: [TSCONFIG_PATH] });
    try {
      const project = snapshot
        .getProjects()
        .find(
          (candidate) =>
            resolve(candidate.configFileName) === resolve(TSCONFIG_PATH),
        );
      expect(project).toBeDefined();
      const missing = typeScriptFiles(EMAIL_TOOLS_PATH).filter(
        (filePath) => project?.program.getSourceFile(filePath) === undefined,
      );

      expect(missing).toEqual([]);
    } finally {
      snapshot.dispose();
      api.close();
    }
  });

  it("parses every production module reference and rejects email tooling", () => {
    const references = moduleReferencesFromFiles(
      typeScriptFiles(PRODUCTION_SOURCE_PATH),
    );
    const violations = references
      .filter(
        (reference) =>
          (reference.kind === "dynamic-import" &&
            reference.specifier === null) ||
          isNodemailerSpecifier(reference.specifier) ||
          isTestMailToolSpecifier(reference.specifier),
      )
      .map((reference) => ({
        file: reference.filePath,
        kind: reference.kind,
        specifier: reference.specifier,
      }));

    expect(violations).toEqual([]);
  });

  it("never PATCHes VAPI or enables mail dispatch from production source", () => {
    for (const filePath of typeScriptFiles(PRODUCTION_SOURCE_PATH)) {
      const text = readFileSync(filePath, "utf8");
      expect(text).not.toMatch(/method:\s*["']PATCH["']/);
      expect(text).not.toMatch(/MAIL_DISPATCH/);
      expect(text).not.toMatch(/lucaplus\.com|inpgroup\.com\.au/i);
    }
  });

  it("proves every Nodemailer import is guarded in a dedicated entrypoint", () => {
    const references = moduleReferencesFromFiles(
      typeScriptFiles(EMAIL_TOOLS_PATH),
    );
    const allowedEntrypoints = [
      resolve(EMAIL_ENTRYPOINT_PATH),
      resolve(TRIAL_EMAIL_ENTRYPOINT_PATH),
    ];
    const dynamicImports = references.filter(
      (reference) => reference.kind === "dynamic-import",
    );
    const staticNodemailer = references.filter(
      (reference) =>
        reference.kind !== "dynamic-import" &&
        isNodemailerSpecifier(reference.specifier),
    );

    expect(
      staticNodemailer.map((reference) => ({
        file: resolve(reference.filePath),
        specifier: reference.specifier,
      })),
    ).toEqual([{
      file: resolve(SMTP_TRANSPORT_PATH),
      specifier: "nodemailer",
    }]);
    expect(
      dynamicImports.map((reference) => ({
        file: resolve(reference.filePath),
        specifier: reference.specifier,
      })),
    ).toEqual(
      allowedEntrypoints.map((file) => ({
        file,
        specifier: "nodemailer",
      })),
    );

    for (const nodemailerLoad of dynamicImports) {
      expect(entrypointExecutionPolicyViolations(nodemailerLoad)).toEqual([]);
    }
  });

  it.each([
    {
      name: "static import",
      source:
        'import mailer from "nodemailer";\nawait import("nodemailer");\nvoid mailer;',
    },
    {
      name: "computed import",
      source:
        'await import("nodemailer");\nawait import("node" + "mailer");',
    },
    {
      name: "subpath import",
      source:
        'await import("nodemailer");\nawait import("nodemailer/lib/smtp-transport");',
    },
    {
      name: "type import",
      source:
        'await import("nodemailer");\ntype Mailer = typeof import("nodemailer");',
    },
  ])("rejects a $name alternative", ({ source }) => {
    const references = moduleReferencesFromSource(source);

    expect(toolImportPolicyViolations(references)).not.toEqual([]);
  });

  it.each([
    {
      name: "else-branch import",
      source: `
        if (isEntrypoint()) {
        } else {
          void (async () => {
            try {
              assertEmailTestEnvironment(process.env);
            } catch {
              return;
            }
            await import("nodemailer");
          })();
        }
      `,
    },
    {
      name: "import in a nested unused callback",
      source: `
        if (isEntrypoint()) {
          void (async () => {
            const neverCalled = async () => {
              assertEmailTestEnvironment(process.env);
              await import("nodemailer");
            };
            void neverCalled;
          })();
        }
      `,
    },
    {
      name: "assertion in a nested unused callback",
      source: `
        if (isEntrypoint()) {
          void (async () => {
            const neverCalled = () => {
              assertEmailTestEnvironment(process.env);
            };
            await import("nodemailer");
            void neverCalled;
          })();
        }
      `,
    },
    {
      name: "dead conditional import",
      source: `
        if (isEntrypoint()) {
          void (async () => {
            if (false) {
              assertEmailTestEnvironment(process.env);
              await import("nodemailer");
            }
          })();
        }
      `,
    },
    {
      name: "assertion after import",
      source: `
        if (isEntrypoint()) {
          void (async () => {
            await import("nodemailer");
            assertEmailTestEnvironment(process.env);
          })();
        }
      `,
    },
  ])("rejects the $name execution mutation", ({ source }) => {
    const references = moduleReferencesFromSource(source);
    const nodemailerLoad = references.find(
      (reference) => reference.kind === "dynamic-import",
    );

    expect(nodemailerLoad).toBeDefined();
    if (!nodemailerLoad) {
      return;
    }
    expect(entrypointExecutionPolicyViolations(nodemailerLoad)).not.toEqual(
      [],
    );
  });

  it.each([
    ["fictional email", EMAIL_WRAPPER_PATH],
    ["LucaPlus trial", TRIAL_EMAIL_WRAPPER_PATH],
  ])("parses the secure %s PowerShell wrapper without errors", (_name, wrapperPath) => {
    const command = [
      "$ErrorActionPreference = 'Stop'",
      "$tokens = $null",
      "$errors = $null",
      "[System.Management.Automation.Language.Parser]::ParseFile(",
      "  $env:WRAPPER_UNDER_TEST,",
      "  [ref]$tokens,",
      "  [ref]$errors",
      ") | Out-Null",
      "if ($errors.Count) {",
      "  $errors | ForEach-Object { Write-Error $_ }",
      "  exit 1",
      "}",
    ].join("\n");
    const result = spawnSync(
      POWERSHELL,
      ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
      {
        encoding: "utf8",
        env: emailTestEnvironment({
          WRAPPER_UNDER_TEST: wrapperPath,
        }),
      },
    );

    expect(result.error).toBeUndefined();
    expect(result.status).toBe(0);
    expect(result.stderr).toBe("");
  });

  it("runs silent npm against the absolute package root from a foreign CWD", () => {
    const scenario = runWrapperScenario({ mode: "success" });
    const stdout = scenario.result.stdout.replaceAll("\r\n", "\n");
    const capture = scenario.capture?.replaceAll("\r\n", "\n");

    expect(scenario.result.error).toBeUndefined();
    expect(scenario.result.status).toBe(0);
    expect(stdout).toBe('{"status":"sent"}\n');
    expect(scenario.result.stderr).toBe("");
    expect(scenario.ui).toContain("From: yinoagent@gmail.com");
    expect(scenario.ui).toContain("To:   867542127@qq.com");
    expect(scenario.securePrompted).toBe(true);
    expect(capture).toBe(
      [
        `cwd=${scenario.foreignCwd}`,
        "arg1=--silent",
        "arg2=--prefix",
        `arg3=${resolve(PACKAGE_ROOT)}`,
        "arg4=run",
        "arg5=test:email",
        "confirmation=SEND 867542127@qq.com",
        "credential=present",
        "",
      ].join("\n"),
    );
  });

  it("maps cancellation to one fixed code without requesting the password", () => {
    const scenario = runWrapperScenario({ mode: "cancel" });

    expect(scenario.result.error).toBeUndefined();
    expect(scenario.result.status).toBe(1);
    expect(scenario.result.stdout.replaceAll("\r\n", "\n")).toBe(
      "email_test_not_confirmed\n",
    );
    expect(scenario.result.stderr).toBe("");
    expect(scenario.capture).toBeNull();
    expect(scenario.securePrompted).toBe(false);
  });

  it("maps an npm launcher throw without formatted exception leakage", () => {
    const scenario = runWrapperScenario({ mode: "launcher-throw" });
    const visibleOutput = `${scenario.result.stdout}\n${scenario.result.stderr}`;

    expect(scenario.result.error).toBeUndefined();
    expect(scenario.result.status).toBe(1);
    expect(scenario.result.stdout.replaceAll("\r\n", "\n")).toBe(
      "email_test_send_failed\n",
    );
    expect(scenario.result.stderr).toBe("");
    expect(visibleOutput).not.toContain("sensitive-launcher-exception");
    expect(visibleOutput).not.toContain("Write-Error");
    expect(scenario.capture).toBeNull();
    expect(scenario.securePrompted).toBe(true);
  });

  it("maps noisy npm failure to one fixed code and preserves its exit code", () => {
    const scenario = runWrapperScenario({ mode: "nonzero" });
    const visibleOutput = `${scenario.result.stdout}\n${scenario.result.stderr}`;

    expect(scenario.result.error).toBeUndefined();
    expect(scenario.result.status).toBe(7);
    expect(scenario.result.stdout.replaceAll("\r\n", "\n")).toBe(
      "email_test_send_failed\n",
    );
    expect(scenario.result.stderr).toBe("");
    expect(visibleOutput).not.toContain("sensitive-child-stdout");
    expect(visibleOutput).not.toContain("sensitive-child-stderr");
    expect(scenario.capture).not.toBeNull();
    expect(scenario.securePrompted).toBe(true);
  });

  it("maps malformed child output with exit zero to one fixed error", () => {
    const scenario = runWrapperScenario({ mode: "malformed-zero" });
    const visibleOutput = `${scenario.result.stdout}\n${scenario.result.stderr}`;

    expect(scenario.result.error).toBeUndefined();
    expect(scenario.result.status).toBe(1);
    expect(scenario.result.stdout.replaceAll("\r\n", "\n")).toBe(
      "email_test_send_failed\n",
    );
    expect(scenario.result.stderr).toBe("");
    expect(visibleOutput).not.toContain("sensitive-malformed-child-output");
    expect(scenario.capture).not.toBeNull();
    expect(scenario.securePrompted).toBe(true);
  });

  it("resolves the package before the password and conditionally zeroes the BSTR", () => {
    const wrapperSource = readFileSync(EMAIL_WRAPPER_PATH, "utf8");
    const packageRootIndex = wrapperSource.indexOf("$packageRoot");
    const passwordPromptIndex = wrapperSource.indexOf(
      'Read-Host "Gmail application password" -AsSecureString',
    );

    expect(packageRootIndex).toBeGreaterThanOrEqual(0);
    expect(passwordPromptIndex).toBeGreaterThan(packageRootIndex);
    expect(wrapperSource).toContain("$passwordPtr = [IntPtr]::Zero");
    expect(wrapperSource).toMatch(
      /try\s*\{[\s\S]*\$passwordPtr\s*=\s*\[Runtime\.InteropServices\.Marshal\]::SecureStringToBSTR\(\$securePassword\)[\s\S]*npm --silent --prefix \$packageRoot run test:email[\s\S]*\}\s*catch\s*\{[\s\S]*\}\s*finally\s*\{[\s\S]*Remove-Item Env:REAL_EMAIL_TEST_CONFIRM[\s\S]*Remove-Item Env:GMAIL_TEST_APP_PASSWORD[\s\S]*if\s*\(\$passwordPtr -ne \[IntPtr\]::Zero\)\s*\{[\s\S]*ZeroFreeBSTR\(\$passwordPtr\)/,
    );
    expect(wrapperSource).not.toMatch(/Write-Error/i);
    expect(wrapperSource).not.toMatch(/^\s*param\s*\(/im);
    expect(wrapperSource).not.toMatch(/\$args\b/i);
  });

  it("runs the trial wrapper against test:trial-email with DeepSeek and a dummy VAPI key file", () => {
    const scenario = runTrialWrapperScenario({ mode: "success" });
    const stdout = scenario.result.stdout.replaceAll("\r\n", "\n");
    const capture = scenario.capture?.replaceAll("\r\n", "\n");

    expect(scenario.result.error).toBeUndefined();
    expect(scenario.result.status).toBe(0);
    expect(stdout).toBe('{"status":"sent"}\n');
    expect(scenario.result.stderr).toBe("");
    expect(scenario.ui).toContain("From: yinoagent@gmail.com");
    expect(scenario.ui).toContain("To:   867542127@qq.com");
    expect(scenario.ui).toContain(
      "Subject: Call Report for <customer_name> <create_time>",
    );
    expect(scenario.ui).toContain(
      "Subject: [质量分析] Luca AI 评分: <score>/10 - <customer_name>",
    );
    expect(scenario.ui).toContain("Profile: lucaplus");
    expect(scenario.securePrompted).toBe(true);
    expect(capture).toBe(
      [
        `cwd=${scenario.foreignCwd}`,
        "arg1=--silent",
        "arg2=--prefix",
        `arg3=${resolve(PACKAGE_ROOT)}`,
        "arg4=run",
        "arg5=test:trial-email",
        "confirmation=SEND 867542127@qq.com",
        "credential=present",
        "vapi=present",
        "deepseek=present",
        "provider=deepseek",
        "",
      ].join("\n"),
    );
    expect(capture).not.toContain("vapi-test-key");
    expect(capture).not.toContain("sk-test-deepseek-file");
  });

  it("maps trial cancellation without requesting the password", () => {
    const scenario = runTrialWrapperScenario({ mode: "cancel" });

    expect(scenario.result.error).toBeUndefined();
    expect(scenario.result.status).toBe(1);
    expect(scenario.result.stdout.replaceAll("\r\n", "\n")).toBe(
      "trial_not_confirmed\n",
    );
    expect(scenario.result.stderr).toBe("");
    expect(scenario.capture).toBeNull();
    expect(scenario.securePrompted).toBe(false);
  });

  it("maps a missing DeepSeek key before the Gmail prompt", () => {
    const scenario = runTrialWrapperScenario({ mode: "missing-deepseek" });

    expect(scenario.result.error).toBeUndefined();
    expect(scenario.result.status).toBe(1);
    expect(scenario.result.stdout.replaceAll("\r\n", "\n")).toBe(
      "trial_credentials_missing\n",
    );
    expect(scenario.result.stderr).toBe("");
    expect(scenario.capture).toBeNull();
    expect(scenario.securePrompted).toBe(false);
  });

  it("maps a missing VAPI key file before the Gmail prompt", () => {
    const scenario = runTrialWrapperScenario({ mode: "missing-vapi-file" });

    expect(scenario.result.error).toBeUndefined();
    expect(scenario.result.status).toBe(1);
    expect(scenario.result.stdout.replaceAll("\r\n", "\n")).toBe(
      "trial_credentials_missing\n",
    );
    expect(scenario.result.stderr).toBe("");
    expect(scenario.capture).toBeNull();
    expect(scenario.securePrompted).toBe(false);
  });

  it("maps a trial npm launcher throw without formatted exception leakage", () => {
    const scenario = runTrialWrapperScenario({ mode: "launcher-throw" });
    const visibleOutput = `${scenario.result.stdout}\n${scenario.result.stderr}`;

    expect(scenario.result.error).toBeUndefined();
    expect(scenario.result.status).toBe(1);
    expect(scenario.result.stdout.replaceAll("\r\n", "\n")).toBe(
      "trial_send_failed\n",
    );
    expect(scenario.result.stderr).toBe("");
    expect(visibleOutput).not.toContain("sensitive-launcher-exception");
    expect(visibleOutput).not.toContain("Write-Error");
    expect(scenario.capture).toBeNull();
    expect(scenario.securePrompted).toBe(true);
  });

  it("keeps the trial wrapper envelope fixed and zeroes the Gmail BSTR", () => {
    const wrapperSource = readFileSync(TRIAL_EMAIL_WRAPPER_PATH, "utf8");
    const packageRootIndex = wrapperSource.indexOf("$packageRoot");
    const passwordPromptIndex = wrapperSource.indexOf(
      'Read-Host "Gmail application password" -AsSecureString',
    );

    expect(packageRootIndex).toBeGreaterThanOrEqual(0);
    expect(passwordPromptIndex).toBeGreaterThan(packageRootIndex);
    expect(wrapperSource).toContain("$passwordPtr = [IntPtr]::Zero");
    expect(wrapperSource).toContain("C:\\Users\\yino\\vapi api.txt");
    expect(wrapperSource).toContain("C:\\Users\\Public\\ds_api.log");
    expect(wrapperSource).toContain('$env:AI_PROVIDER = "deepseek"');
    expect(wrapperSource).toContain("$env:DEEPSEEK_API_KEY = $deepseekKey");
    expect(wrapperSource).toMatch(
      /try\s*\{[\s\S]*\$passwordPtr\s*=\s*\[Runtime\.InteropServices\.Marshal\]::SecureStringToBSTR\(\$securePassword\)[\s\S]*npm --silent --prefix \$packageRoot run test:trial-email[\s\S]*\}\s*catch\s*\{[\s\S]*\}\s*finally\s*\{[\s\S]*Remove-Item Env:REAL_EMAIL_TEST_CONFIRM[\s\S]*Remove-Item Env:GMAIL_TEST_APP_PASSWORD[\s\S]*if\s*\(\$passwordPtr -ne \[IntPtr\]::Zero\)\s*\{[\s\S]*ZeroFreeBSTR\(\$passwordPtr\)/,
    );
    expect(wrapperSource).not.toMatch(/Write-Error/i);
    expect(wrapperSource).not.toMatch(/^\s*param\s*\(/im);
    expect(wrapperSource).not.toMatch(/\$args\b/i);
  });

  it("runs the complete default Mock pipeline with zero fetch calls", async () => {
    const originalFetch = globalThis.fetch;
    let calls = 0;
    globalThis.fetch = (async () => {
      calls += 1;
      throw new Error("network forbidden in Mock mode");
    }) as typeof fetch;

    try {
      vi.resetModules();
      await runCompleteMockPipeline();
      expect(calls).toBe(0);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

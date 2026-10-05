#requires -Version 5.1
<#
.SYNOPSIS
Launch CPO agent roles sequentially with fresh Codex CLI contexts.
.EXAMPLE
.\scripts\start-agents.ps1 -Roles coding -Preview
.EXAMPLE
.\scripts\start-agents.ps1 -Roles coding,setup_qa,cleanup_db_qa,pomodoro_qa
.EXAMPLE
.\scripts\start-agents.ps1 -Roles debugger
.EXAMPLE
.\scripts\start-agents.ps1 -Roles todo_audit,code_mapping,database_mapping
.NOTES
Run when no other agent is editing this checkout. QA uses the CLI's configured
model/effort unless InheritedModel/InheritedEffort are supplied. This launches
new CLI sessions, not the desktop chat's existing subagents. Account usage
limits remain shared; launching fresh sessions does not reset them.
#>
[CmdletBinding()]
param(
    [ValidateSet('coding','debugger','setup_qa','cleanup_db_qa','pomodoro_qa','todo_audit','code_mapping','database_mapping','design','cicd')]
    [string[]]$Roles = @('coding'),
    [string]$Repository = (Split-Path -Parent $PSScriptRoot),
    [string]$InheritedModel,
    [ValidateSet('low','medium','high','xhigh','max','ultra')]
    [string]$InheritedEffort,
    [switch]$Preview
)

$ErrorActionPreference = 'Stop'
$Repository = (Resolve-Path -LiteralPath $Repository).Path
$profiles = @{
    coding = @('gpt-6.1-sol', 'medium', 'workspace-write', 'Continue unfinished source/test implementation from the compact HANDOFF checkpoint. Preserve all dirty work. Complete approved invitation/audit/validation requirements and run required checks. No remote or production actions.')
    debugger = @('gpt-6.1-sol', 'high', 'workspace-write', 'Read saved QA findings and current dirty code; fix diagnosed defects with regressions. Preserve existing changes. Run affected and full required checks. No remote or production actions.')
    setup_qa = @('', '', 'read-only', 'Read-only setup, default-role, authority, invitation security, and private-log QA. Exercise failure and race cases. Report actionable findings; never edit source or governance.')
    cleanup_db_qa = @('', '', 'read-only', 'Read-only database, migration, persistence, audit, invitation CAS/restart, teardown, cancellation and cleanup QA. Use temporary SQLite databases. Report findings; never edit source or governance.')
    pomodoro_qa = @('', '', 'read-only', 'Read-only timer, invitation deadline/admission, check-in lifecycle, recovery, task ownership and focus provenance QA. Report findings; never edit source or governance.')
    todo_audit = @('gpt-6.1-sol', 'low', 'read-only', 'Read-only evidence audit of checked TODO claims against current source and verification. Report unsupported claims and scope limits.')
    code_mapping = @('gpt-6-luna', 'low', 'workspace-write', 'Only after implementation and QA are verified, retrace final source and rebuild ARCHITECTURE.md with concise Mermaid diagrams. Documentation only; never edit runtime source or tests. If verification is missing, return needs_work.')
    database_mapping = @('gpt-6-luna', 'low', 'workspace-write', 'Only after implementation and QA are verified, retrace final database schema/DAL and create database_architecture.md with Mermaid diagrams. Documentation only; never edit runtime source or tests. If verification is missing, return needs_work.')
    design = @('', '', 'read-only', 'Investigate an unresolved system/architecture decision. Design and findings only; no implementation or remote actions.')
    cicd = @('', '', 'workspace-write', 'Inspect current verification and packaging. Follow saved remote authorization precisely; branch pushes only after final checks. Never move immutable rc.5 tags, replace assets, merge, force-push or deploy to Discord. If evidence/authorization is insufficient, return needs_work.')
}

foreach ($file in @('AGENTS.md','RESUME_WORKFLOW.md','HANDOFF.md')) {
    if (-not (Test-Path -LiteralPath (Join-Path $Repository $file))) {
        throw "Missing required checkpoint: $file"
    }
}
if ($Roles.Count -ne (@($Roles | Select-Object -Unique)).Count) {
    throw 'Select each role once per invocation.'
}
$codexCommand = Get-Command codex -ErrorAction Stop
$common = @'
Read AGENTS.md, RESUME_WORKFLOW.md, the latest compact HANDOFF checkpoint,
KNOWLEDGE_GRAPH.md and KNOWN_ISSUES.md before acting. This invocation authorizes
only the selected role. Use fresh context, preserve dirty files, and run no
other agents. Current approvals persist; do not request them again. No secrets,
new dependencies, unapproved schemas/signatures, or live Discord operations.
Honor sequential ownership and current permission/default-role policy.
QA is read-only; run tests using temporary files and disable repository caches.
Return passed only when this role's authorized work and required checks are
complete; otherwise return needs_work with precise findings and remaining work.
Do not claim earlier staged verification covers unfinished edits.
'@

if ($Preview) {
    foreach ($role in $Roles) {
        $profile = $profiles[$role]
        $model = if ($profile[0]) { $profile[0] } elseif ($InheritedModel) { $InheritedModel } else { 'CLI configured default' }
        $effort = if ($profile[1]) { $profile[1] } elseif ($InheritedEffort) { $InheritedEffort } else { 'CLI configured default' }
        Write-Output "$role : model=$model; effort=$effort; sandbox=$($profile[2])"
    }
    return
}

$runRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('cpo-agent-runs-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runRoot | Out-Null
$schemaPath = Join-Path $runRoot 'result-schema.json'
$schema = @'
{"type":"object","properties":{"status":{"type":"string","enum":["passed","needs_work"]},"summary":{"type":"string"},"findings":{"type":"array","items":{"type":"string"}}},"required":["status","summary","findings"],"additionalProperties":false}
'@
[System.IO.File]::WriteAllText($schemaPath, $schema, [System.Text.UTF8Encoding]::new($false))
Write-Output "Agent reports: $runRoot"

foreach ($role in $Roles) {
    $profile = $profiles[$role]
    $model = if ($profile[0]) { $profile[0] } else { $InheritedModel }
    $effort = if ($profile[1]) { $profile[1] } else { $InheritedEffort }
    $reportPath = Join-Path $runRoot "$role.json"
    $arguments = @('exec','--cd',$Repository,'--sandbox',$profile[2],'--output-schema',$schemaPath,'--output-last-message',$reportPath)
    if ($model) { $arguments += @('--model',$model) }
    if ($effort) { $arguments += @('--config',"model_reasoning_effort=`"$effort`"") }
    $prompt = "$common`nRole: $role`n$($profile[3])`nEarlier role reports in this run: $runRoot`n"
    Write-Output "Starting $role (sequential)."
    $prompt | & $codexCommand.Source @arguments -
    if ($LASTEXITCODE -ne 0) {
        throw "$role failed with exit code $LASTEXITCODE. No model substitution or next role was attempted. Reports: $runRoot"
    }
    if (-not (Test-Path -LiteralPath $reportPath)) { throw "$role did not produce a report." }
    $result = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    Write-Output $result.summary
    if ($result.status -ne 'passed') {
        throw "$role needs work. Review $reportPath before starting later roles."
    }
}

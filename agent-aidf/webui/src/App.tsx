import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Textarea } from "@/components/ui/textarea"

type PhaseState = "done" | "current" | "pending"

interface Phase {
  order: number
  name: string
  human_role: string
  ai_role: string
  deliverables: string[]
  exit_criteria: string
  state: PhaseState
}

interface Status {
  project_root: string
  repo_root: string
  has_kaidf: boolean
  pack_count: number
  mentor_step_count: number
  mentor_pending_category: string | null
  mentor_current_app_url: string | null
  current_phase: number
  total_phases: number
  phases: Phase[]
}

interface MentorResponse extends Status {
  message: string
  pending_question: string | null
  current_app_id: string | null
}

const STATE_BADGE: Record<PhaseState, { label: string; variant: "accent" | "default" | "outline" }> = {
  done: { label: "Done", variant: "default" },
  current: { label: "Current", variant: "accent" },
  pending: { label: "Pending", variant: "outline" },
}

async function getStatus(): Promise<Status> {
  const response = await fetch("/api/status")
  if (!response.ok) throw new Error(`GET /api/status -> ${response.status}`)
  return response.json()
}

async function postMentor(answer: string | null): Promise<MentorResponse> {
  const response = await fetch("/api/mentor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  })
  if (!response.ok) throw new Error(`POST /api/mentor -> ${response.status}`)
  return response.json()
}

async function postExit(): Promise<void> {
  await fetch("/api/exit", { method: "POST" })
}

function PhaseCard({ phase }: { phase: Phase }) {
  const badge = STATE_BADGE[phase.state]
  return (
    <Card className={phase.state === "current" ? "border-primary" : undefined}>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle>
            {phase.order}. {phase.name}
          </CardTitle>
          <Badge variant={badge.variant}>{badge.label}</Badge>
        </div>
        <CardDescription>{phase.exit_criteria}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-xs">
        <p>
          <span className="text-muted-foreground">Human: </span>
          {phase.human_role}
        </p>
        <p>
          <span className="text-muted-foreground">AI: </span>
          {phase.ai_role}
        </p>
        <p className="text-muted-foreground">Deliverables: {phase.deliverables.join(", ")}</p>
      </CardContent>
    </Card>
  )
}

export default function App() {
  const [status, setStatus] = useState<Status | null>(null)
  const [log, setLog] = useState<string[]>([
    "Welcome to the kob web UI. Type an answer to chat with the mentor, or use /status, /mentor, /exit.",
  ])
  const [input, setInput] = useState("")
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null)
  const [exited, setExited] = useState(false)
  const [busy, setBusy] = useState(false)
  const logEndRef = useRef<HTMLDivElement | null>(null)

  const appendLog = useCallback((line: string) => {
    setLog((prev) => [...prev.slice(-200), line])
  }, [])

  const refreshStatus = useCallback(async () => {
    try {
      const next = await getStatus()
      setStatus(next)
    } catch {
      // the server may be mid-shutdown; ignore transient poll failures
    }
  }, [])

  useEffect(() => {
    refreshStatus()
    const interval = setInterval(() => {
      if (!exited) refreshStatus()
    }, 5000)
    return () => clearInterval(interval)
  }, [refreshStatus, exited])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "end" })
  }, [log])

  const runCommand = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || busy) return

      if (trimmed === "/exit") {
        appendLog("> " + trimmed)
        setBusy(true)
        await postExit()
        appendLog("Session ended. You can close this tab.")
        setExited(true)
        setBusy(false)
        return
      }

      appendLog("> " + trimmed)
      setBusy(true)
      try {
        if (trimmed === "/status") {
          const next = await getStatus()
          setStatus(next)
          appendLog(
            `Phase ${next.current_phase}/${next.total_phases} - pack_count=${next.pack_count} mentor_step_count=${next.mentor_step_count}`,
          )
        } else if (trimmed.startsWith("/mentor")) {
          const answer = trimmed.slice("/mentor".length).trim() || null
          const next = await postMentor(answer)
          setStatus(next)
          setPendingQuestion(next.pending_question)
          appendLog(next.message)
        } else {
          const next = await postMentor(trimmed)
          setStatus(next)
          setPendingQuestion(next.pending_question)
          appendLog(next.message)
        }
      } catch (error) {
        appendLog(`Error running command: ${(error as Error).message}`)
      } finally {
        setBusy(false)
      }
    },
    [appendLog, busy],
  )

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    const text = input
    setInput("")
    runCommand(text)
  }

  return (
    <div className="mx-auto flex h-screen max-w-5xl flex-col gap-4 p-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <CardTitle className="text-lg text-primary">Kob Agent - Maturity Model</CardTitle>
            <span className="text-xs text-muted-foreground">{status?.project_root}</span>
          </div>
          <CardDescription>
            {status
              ? `Phase ${status.current_phase}/${status.total_phases}${
                  status.mentor_pending_category ? ` - pending: ${status.mentor_pending_category}` : ""
                }`
              : "Loading status..."}
          </CardDescription>
          <Progress value={status ? (status.current_phase / status.total_phases) * 100 : 0} />
        </CardHeader>
      </Card>

      <div className="grid grid-cols-1 gap-3 overflow-y-auto md:grid-cols-2 lg:grid-cols-3">
        {status?.phases.map((phase) => <PhaseCard key={phase.order} phase={phase} />)}
      </div>

      <Card className="flex-1 overflow-hidden">
        <CardHeader>
          <CardTitle>Mentor</CardTitle>
          {pendingQuestion && <CardDescription>{pendingQuestion}</CardDescription>}
        </CardHeader>
        <CardContent className="flex h-full flex-col gap-2 overflow-y-auto pt-0 text-sm">
          {log.map((line, index) => (
            <p key={index} className="whitespace-pre-wrap text-muted-foreground">
              {line}
            </p>
          ))}
          <div ref={logEndRef} />
        </CardContent>
      </Card>

      <form onSubmit={onSubmit} className="flex gap-2">
        <Textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault()
              onSubmit(event)
            }
          }}
          placeholder="Type an answer, or a command (/status, /mentor, /exit)..."
          disabled={exited}
          className="min-h-10"
        />
        <Button type="submit" disabled={exited || busy}>
          Send
        </Button>
      </form>

      {exited && (
        <div className="fixed inset-0 flex items-center justify-center bg-background/90">
          <Card>
            <CardHeader>
              <CardTitle>Session ended</CardTitle>
              <CardDescription>The kob web UI server has stopped. You can close this tab.</CardDescription>
            </CardHeader>
          </Card>
        </div>
      )}
    </div>
  )
}

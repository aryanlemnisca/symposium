import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ReactFlow, Background, BackgroundVariant, type Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useSessionStore, type SessionSettings } from '../store/sessionStore';
import { useCanvasStore, type AgentNodeData } from '../store/canvasStore';
import { useWebSocket } from '../hooks/useWebSocket';
import { api } from '../api/client';
import AgentNode from '../components/canvas/AgentNode';
import AgentDrawer from '../components/canvas/AgentDrawer';
import AgentLibrary from '../components/canvas/AgentLibrary';
import ProblemStatement from '../components/setup/ProblemStatement';
import ModeSelector from '../components/setup/ModeSelector';
import AdvancedSettings from '../components/setup/AdvancedSettings';
import DocumentUpload from '../components/setup/DocumentUpload';
import PhaseCards from '../components/setup/PhaseCards';
import LiveFeed from '../components/session/LiveFeed';
import ArtifactPanel from '../components/session/ArtifactPanel';
import StatsBar from '../components/session/StatsBar';
import DocumentSidebar from '../components/session/DocumentSidebar';
import type { UploadedDocument, Phase } from '../store/sessionStore';

const nodeTypes = { agentNode: AgentNode };

const defaultSettings: SessionSettings = {
  max_rounds: 50,
  temperature: 0.70,
  gate_start_round: 10,
  overseer_interval: 10,
  min_rounds_before_convergence: 45,
  prd_panel_rounds: 10,
};

interface SuggestedAgent {
  name: string;
  persona: string;
  model: string;
  role_tag: string;
  mission?: string;
  rationale?: string;
}

export default function Canvas() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentSession, fetchSession, updateSession } = useSessionStore();
  const { nodes, edges, onNodesChange, onEdgesChange, selectNode, addAgent, reset: resetCanvas } = useCanvasStore();

  const [problemStatement, setProblemStatement] = useState('');
  const [mode, setMode] = useState('product');
  const [settings, setSettings] = useState<SessionSettings>(defaultSettings);
  const [isLive, setIsLive] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // AI suggest agents
  const [suggestingAgents, setSuggestingAgents] = useState(false);
  const [suggestedAgents, setSuggestedAgents] = useState<SuggestedAgent[]>([]);

  // Stress test state
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDocument[]>([]);
  const [phases, setPhases] = useState<Phase[]>([]);
  const [phasesConfirmed, setPhasesConfirmed] = useState(false);
  const [reviewInstructions, setReviewInstructions] = useState('');
  const [analysing, setAnalysing] = useState(false);
  const [reinterpreting, setReinterpreting] = useState(false);

  // Pre-run confirmation + PRD panel
  const [showConfirm, setShowConfirm] = useState(false);
  const [prdPanelNames, setPrdPanelNames] = useState<string[]>([]);
  const [prdRationale, setPrdRationale] = useState<Record<string, string>>({});
  const [prdProductAgent, setPrdProductAgent] = useState<string>('');
  const [loadingPrdSuggest, setLoadingPrdSuggest] = useState(false);

  const { connect, connected: _connected, messages: wsMessages } = useWebSocket({
    sessionId: id || '',
    onMessage: (msg) => {
      if (msg.type === 'agent_message' && msg.streaming) {
        // Agent starts speaking — activate glow
        useCanvasStore.getState().setActiveAgent(msg.source as string);
      }
      if (msg.type === 'agent_message_chunk') {
        // Keep glow active during streaming
        useCanvasStore.getState().setActiveAgent(msg.source as string);
      }
      if (msg.type === 'agent_message' && !msg.streaming) {
        // Agent finished — clear glow
        useCanvasStore.getState().setActiveAgent(null);
      }
      if (msg.type === 'session_complete') {
        useCanvasStore.getState().setActiveAgent(null);
        setTimeout(() => navigate(`/results/${id}`), 2000);
      }
      if (msg.type === 'session_stopped') {
        useCanvasStore.getState().setActiveAgent(null);
        setIsLive(false);
      }
    },
  });

  useEffect(() => {
    resetCanvas();
    setLoaded(false);
    if (id) fetchSession(id);
  }, [id, fetchSession, resetCanvas]);

  useEffect(() => {
    if (currentSession && !loaded) {
      setProblemStatement(currentSession.problem_statement || '');
      setMode(currentSession.mode || 'product');
      setSettings({ ...defaultSettings, ...currentSession.settings });
      if (currentSession.agents?.length > 0) {
        currentSession.agents.forEach((agent) => {
          addAgent(
            { id: agent.id, name: agent.name, model: agent.model, persona: agent.persona, tools: agent.tools, role_tag: agent.role_tag },
            agent.canvas_position || { x: 250, y: 250 },
          );
        });
      }
      // Restore stress test state
      if (currentSession.uploaded_documents?.length) {
        setUploadedDocs(currentSession.uploaded_documents);
      }
      if (currentSession.phases?.length) {
        setPhases(currentSession.phases);
        setPhasesConfirmed(currentSession.phases.some((p) => p.status !== undefined));
      }
      if (currentSession.stress_review_instructions) {
        setReviewInstructions(currentSession.stress_review_instructions);
      }
      setLoaded(true);
    }
  }, [currentSession, loaded, addAgent]);

  const handleSave = useCallback(async () => {
    if (!id) return;
    const agentConfigs = nodes.map((n: Node<AgentNodeData>) => ({
      id: n.id, name: n.data.name, model: n.data.model, persona: n.data.persona,
      tools: n.data.tools, role_tag: n.data.role_tag, canvas_position: n.position,
    }));
    // Auto-name from problem statement if still "New Session"
    const autoName = currentSession?.name === 'New Session' && problemStatement
      ? problemStatement.split('\n')[0].slice(0, 60).trim() || 'New Session'
      : undefined;
    await updateSession(id, {
      ...(autoName ? { name: autoName } : {}),
      problem_statement: problemStatement,
      mode: mode as SessionSettings['temperature'] extends number ? 'product' | 'problem' : never,
      agents: agentConfigs as any,
      settings,
    });
  }, [id, nodes, problemStatement, mode, settings, updateSession, currentSession?.name]);

  const handleSuggestAgents = async () => {
    if (!problemStatement || problemStatement.length < 20) return;
    setSuggestingAgents(true);
    setSuggestedAgents([]);
    try {
      const res = await api.post<{ agents: SuggestedAgent[] }>('/suggest/agents', {
        problem_statement: problemStatement,
        mode,
      });
      setSuggestedAgents(res.agents || []);
    } catch {
      // ignore
    } finally {
      setSuggestingAgents(false);
    }
  };

  const handleAnalyseDocuments = async () => {
    if (!id) return;
    await updateSession(id, {
      uploaded_documents: uploadedDocs as any,
      problem_statement: problemStatement,
      mode: mode as any,
    });
    setAnalysing(true);
    try {
      const res = await api.post<{ phases: Phase[]; review_instructions: string }>(`/sessions/${id}/stress/analyse-documents`);
      // Build a filename→id lookup to map AI-returned filenames to actual doc IDs
      const filenameToId: Record<string, string> = {};
      uploadedDocs.forEach((d) => {
        filenameToId[d.filename] = d.id;
        filenameToId[d.filename.replace(/\.[^.]+$/, '')] = d.id; // also match without extension
      });

      const phasesWithIds = (res.phases || []).map((p: any, i: number) => {
        const schema = Array.isArray(p.artifact_schema) ? p.artifact_schema
          : typeof p.artifact_schema === 'string' ? p.artifact_schema.split('\n').filter(Boolean)
          : [];

        // Map document references to actual IDs (AI may return filenames instead of UUIDs)
        const rawDocIds = p.document_ids || [];
        const resolvedDocIds = rawDocIds.map((ref: string) => {
          if (filenameToId[ref]) return filenameToId[ref]; // exact filename match
          // fuzzy match — check if any uploaded doc filename contains this ref or vice versa
          const match = uploadedDocs.find((d) =>
            d.filename.includes(ref) || ref.includes(d.filename) || d.id === ref
          );
          return match ? match.id : ref;
        });

        return {
          ...p,
          number: i + 1,
          status: 'pending' as const,
          document_ids: resolvedDocIds.length > 0 ? resolvedDocIds : uploadedDocs.map((d) => d.id),
          key_subquestions: p.key_subquestions || [],
          artifact_schema: schema,
          start_round: null,
          end_round: null,
          artifact: null,
          confirmed: [],
          contested: [],
          open_questions: [],
        };
      });
      setPhases(phasesWithIds);
      setReviewInstructions(res.review_instructions || '');
    } catch {
      // ignore
    } finally {
      setAnalysing(false);
    }
  };

  const handleReinterpret = async () => {
    if (!id) return;
    setReinterpreting(true);
    try {
      const res = await api.post<{ phases: Phase[] }>(`/sessions/${id}/stress/reinterpret-phases`, { phases });
      if (res.phases) {
        setPhases(res.phases.map((p: any, i: number) => ({ ...p, number: i + 1 })));
      }
    } catch {
      // ignore
    } finally {
      setReinterpreting(false);
    }
  };

  const handleAnalyseProblem = async () => {
    if (!problemStatement || problemStatement.length < 20) return;
    setAnalysing(true);
    try {
      const res = await api.post<{ phases: Phase[] }>('/suggest/phases', {
        problem_statement: problemStatement,
        mode,
      });
      const phasesWithDefaults = (res.phases || []).map((p: any, i: number) => {
        const schema = Array.isArray(p.artifact_schema) ? p.artifact_schema
          : typeof p.artifact_schema === 'string' ? p.artifact_schema.split('\n').filter(Boolean)
          : [];
        return {
          ...p,
          number: i + 1,
          status: 'pending' as const,
          document_ids: [],
          key_subquestions: p.key_subquestions || [],
          artifact_schema: schema,
          start_round: null,
          end_round: null,
          artifact: null,
          confirmed: [],
          contested: [],
          open_questions: [],
        };
      });
      setPhases(phasesWithDefaults);
    } catch {
      // ignore
    } finally {
      setAnalysing(false);
    }
  };

  const handleConfirmPhasesGeneric = async () => {
    if (!id) return;
    await updateSession(id, { phases: phases as any });
    setPhasesConfirmed(true);

    // Auto-set max_rounds based on phases
    const minPerPhase = 15;
    const estimatedTotal = phases.length * minPerPhase;
    if (settings.max_rounds < estimatedTotal) {
      setSettings((s) => ({ ...s, max_rounds: Math.round(estimatedTotal * 1.5) }));
    }

    // Auto-suggest agents if none added yet
    if (nodes.length === 0) {
      handleSuggestAgents();
    }
  };

  const handleConfirmPhases = async () => {
    if (!id) return;
    await api.post(`/sessions/${id}/stress/confirm-phases`, { phases, review_instructions: reviewInstructions });
    setPhasesConfirmed(true);

    // Auto-set max_rounds based on phases
    const minPerPhase = settings.stress_test_min_rounds_per_phase || 20;
    const estimatedTotal = phases.length * minPerPhase;
    if (settings.max_rounds < estimatedTotal) {
      setSettings((s) => ({ ...s, max_rounds: Math.round(estimatedTotal * 1.5) }));
    }

    // Auto-suggest agents for stress test
    if (nodes.length === 0) {
      setSuggestingAgents(true);
      try {
        const res = await api.post<{ agents: SuggestedAgent[] }>(`/sessions/${id}/stress/suggest-agents`);
        setSuggestedAgents(res.agents || []);
      } catch {
        // ignore
      } finally {
        setSuggestingAgents(false);
      }
    }
  };

  const acceptSuggestedAgent = (agent: SuggestedAgent) => {
    addAgent(
      { id: '', name: agent.name, model: agent.model || 'gemini-3.1-pro-preview', persona: agent.persona, tools: [], role_tag: agent.role_tag },
      { x: 250, y: 250 },
    );
    setSuggestedAgents((prev) => prev.filter((a) => a.name !== agent.name));
  };

  const acceptAllSuggested = () => {
    suggestedAgents.forEach((agent) => {
      addAgent(
        { id: '', name: agent.name, model: agent.model || 'gemini-3.1-pro-preview', persona: agent.persona, tools: [], role_tag: agent.role_tag },
        { x: 250, y: 250 },
      );
    });
    setSuggestedAgents([]);
  };

  const handleBeginClick = async () => {
    setShowConfirm(true);
    if (mode === 'product' && prdPanelNames.length === 0) {
      setLoadingPrdSuggest(true);
      try {
        const agentData = nodes.map((n) => ({
          name: n.data.name, role_tag: n.data.role_tag, persona: n.data.persona,
        }));
        const res = await api.post<{ selected: string[]; rationale: Record<string, string>; product_agent: string }>('/suggest/prd-panel', {
          agents: agentData,
          problem_statement: problemStatement,
        });
        setPrdPanelNames(res.selected || []);
        setPrdRationale(res.rationale || {});
        setPrdProductAgent(res.product_agent || '');
      } catch {
        // Fallback: first 4
        setPrdPanelNames(nodes.slice(0, 4).map((n) => n.data.name));
      } finally {
        setLoadingPrdSuggest(false);
      }
    }
  };

  const handleConfirmStart = async () => {
    setShowConfirm(false);
    // Inject prd_panel_names into settings before saving
    const finalSettings = {
      ...settings,
      prd_panel_names: prdPanelNames,
      stress_test_min_rounds_per_phase: settings.stress_test_min_rounds_per_phase || 20,
    };
    setSettings(finalSettings);
    if (!id) return;
    const agentConfigs = nodes.map((n: Node<AgentNodeData>) => ({
      id: n.id, name: n.data.name, model: n.data.model, persona: n.data.persona,
      tools: n.data.tools, role_tag: n.data.role_tag, canvas_position: n.position,
    }));
    await updateSession(id, {
      problem_statement: problemStatement,
      mode: mode as any,
      agents: agentConfigs as any,
      settings: finalSettings,
    });
    await api.post(`/sessions/${id}/run`);
    setIsLive(true);
    connect();
  };

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    selectNode(node.id);
  };

  if (!currentSession) {
    return <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--color-navy)', color: 'var(--color-text-dim)' }}>Loading...</div>;
  }

  if (isLive) {
    return (
      <div className="h-screen flex flex-col overflow-hidden" style={{ background: 'var(--color-navy)' }}>
        <div className="flex items-center justify-between px-4" style={{ borderBottom: '1px solid var(--color-border)' }}>
          <StatsBar messages={wsMessages} maxRounds={settings.max_rounds} />
          <button
            onClick={async () => {
              if (!id) return;
              try {
                await api.post(`/sessions/${id}/stop`);
              } catch {}
            }}
            className="px-4 py-1.5 rounded-lg text-xs font-medium shrink-0"
            style={{ background: '#7f1d1d', color: '#fca5a5', border: '1px solid #991b1b' }}
          >
            Stop Run
          </button>
        </div>
        <div className="flex-1 flex min-h-0">
          <div className="w-2/5 h-full" style={{ borderRight: '1px solid var(--color-border)' }}>
            {mode === 'stress_test' && uploadedDocs.length > 0 ? (
              <DocumentSidebar
                documents={uploadedDocs}
                phases={phases}
                currentPhaseIndex={(() => {
                  const latestStats = [...wsMessages].reverse().find((m) => m.type === 'stats');
                  return (latestStats?.phase_number as number || 1) - 1;
                })()}
                messages={wsMessages}
              />
            ) : (
              <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
                <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e2438" />
              </ReactFlow>
            )}
          </div>
          <div className="w-3/5 h-full flex flex-col min-h-0">
            <LiveFeed messages={wsMessages} agents={currentSession?.agents || []} />
            <div className="shrink-0 overflow-y-auto" style={{ height: '30%', borderTop: '1px solid var(--color-border)' }}>
              <ArtifactPanel messages={wsMessages} />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex overflow-hidden" style={{ background: 'var(--color-navy)' }}>
      <div className="w-80 h-full overflow-y-auto shrink-0 p-4 flex flex-col gap-4" style={{ background: 'var(--color-navy-light)', borderRight: '1px solid var(--color-border)' }}>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold" style={{ color: 'var(--color-teal)' }}>Setup</h2>
          <button onClick={() => navigate('/sessions')} className="text-xs" style={{ color: 'var(--color-text-dim)' }}>Back</button>
        </div>
        {mode === 'stress_test' && (
          <DocumentUpload documents={uploadedDocs} onChange={setUploadedDocs} />
        )}
        <ProblemStatement value={problemStatement} onChange={setProblemStatement} mode={mode} />
        <ModeSelector value={mode} onChange={(m) => { setMode(m); if (m !== mode) { setPhases([]); setPhasesConfirmed(false); setSuggestedAgents([]); } }} />

        {/* Analyse Documents button (stress_test only) */}
        {mode === 'stress_test' && uploadedDocs.length > 0 && problemStatement.length > 20 && !phases.length && (
          analysing ? (
            <div className="w-full py-4 rounded-lg text-center" style={{ border: '1px solid var(--color-teal-dim)', background: 'var(--color-navy)' }}>
              <div className="flex items-center justify-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--color-teal)', animationDelay: '0ms' }} />
                <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--color-teal)', animationDelay: '150ms' }} />
                <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--color-teal)', animationDelay: '300ms' }} />
              </div>
              <p className="text-xs" style={{ color: 'var(--color-teal-dim)' }}>Analysing {uploadedDocs.length} documents...</p>
              <p className="text-[10px] mt-1" style={{ color: 'var(--color-text-dim)' }}>Designing review phases and artifact schemas</p>
            </div>
          ) : (
            <button onClick={handleAnalyseDocuments} className="w-full py-2 rounded-lg text-sm" style={{ border: '1px solid var(--color-teal-dim)', color: 'var(--color-teal-dim)' }}>
              Analyse Documents
            </button>
          )
        )}

        {/* Analyse Problem button (product/problem modes) */}
        {mode !== 'stress_test' && problemStatement.length > 20 && !phases.length && (
          analysing ? (
            <div className="w-full py-4 rounded-lg text-center" style={{ border: '1px solid var(--color-teal-dim)', background: 'var(--color-navy)' }}>
              <div className="flex items-center justify-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--color-teal)', animationDelay: '0ms' }} />
                <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--color-teal)', animationDelay: '150ms' }} />
                <div className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--color-teal)', animationDelay: '300ms' }} />
              </div>
              <p className="text-xs" style={{ color: 'var(--color-teal-dim)' }}>Analysing problem statement...</p>
              <p className="text-[10px] mt-1" style={{ color: 'var(--color-text-dim)' }}>Designing discussion phases</p>
            </div>
          ) : (
            <button onClick={handleAnalyseProblem} className="w-full py-2 rounded-lg text-sm" style={{ border: '1px solid var(--color-teal-dim)', color: 'var(--color-teal-dim)' }}>
              Analyse Problem
            </button>
          )
        )}

        {/* Suggest Agents button */}
        {mode !== 'stress_test' && phasesConfirmed && (
        <button
          onClick={handleSuggestAgents}
          disabled={suggestingAgents || problemStatement.length < 20}
          className="w-full py-2 rounded-lg text-sm disabled:opacity-40"
          style={{ border: '1px solid var(--color-teal-dim)', color: 'var(--color-teal-dim)' }}
        >
          {suggestingAgents ? 'Generating agents...' : 'Suggest Agents'}
        </button>
        )}

        {/* Suggested agents list */}
        {suggestedAgents.length > 0 && (
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium" style={{ color: 'var(--color-teal)' }}>Suggested Agents</span>
              <button onClick={acceptAllSuggested} className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>Add All</button>
            </div>
            {suggestedAgents.map((agent) => (
              <div key={agent.name} className="p-3 rounded-lg text-xs" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)' }}>
                <div className="flex justify-between items-start mb-1">
                  <div>
                    <span className="font-medium" style={{ color: 'var(--color-text)' }}>{agent.name.replace(/_/g, ' ')}</span>
                    {agent.role_tag && <span className="ml-2 text-[10px]" style={{ color: 'var(--color-teal-dim)' }}>{agent.role_tag}</span>}
                  </div>
                  <button onClick={() => acceptSuggestedAgent(agent)} className="text-[10px] px-2 py-0.5 rounded shrink-0" style={{ border: '1px solid var(--color-teal-dim)', color: 'var(--color-teal-dim)' }}>Add</button>
                </div>
                {agent.rationale && <p style={{ color: 'var(--color-text-dim)' }}>{agent.rationale}</p>}
              </div>
            ))}
            <button onClick={() => setSuggestedAgents([])} className="w-full text-[10px] py-1" style={{ color: 'var(--color-text-dim)' }}>Dismiss suggestions</button>
          </div>
        )}

        <AdvancedSettings settings={settings} onChange={setSettings} mode={mode} phaseCount={phases.length} />
        <button onClick={handleSave} className="w-full py-2 rounded-lg text-sm" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>Save Draft</button>
        <button onClick={handleBeginClick} disabled={!problemStatement || nodes.length < 2 || !phasesConfirmed} className="w-full py-3 rounded-lg font-bold text-sm transition-colors disabled:opacity-40" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>Begin Symposium</button>
        {nodes.length < 2 && (<p className="text-[10px]" style={{ color: '#fbbf24' }}>Add at least 2 agents to begin</p>)}
      </div>
      <div className="flex-1 h-full">
        {phases.length > 0 && !phasesConfirmed ? (
          <div className="h-full overflow-y-auto p-6">
            <PhaseCards
              phases={phases}
              onChange={setPhases}
              onReinterpret={mode === 'stress_test' ? handleReinterpret : handleAnalyseProblem}
              onConfirm={mode === 'stress_test' ? handleConfirmPhases : handleConfirmPhasesGeneric}
              reinterpreting={mode === 'stress_test' ? reinterpreting : analysing}
              confirmed={phasesConfirmed}
            />
            {mode === 'stress_test' && reviewInstructions && (
              <div className="mt-4">
                <label className="text-[10px] block mb-1 uppercase tracking-wider" style={{ color: 'var(--color-text-dim)' }}>Review Instructions (editable)</label>
                <textarea
                  value={reviewInstructions}
                  onChange={(e) => setReviewInstructions(e.target.value)}
                  rows={8}
                  className="w-full px-3 py-2 rounded-lg text-xs outline-none resize-y"
                  style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)', fontFamily: 'monospace' }}
                />
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1 h-full flex flex-col min-h-0">
            {/* Compact phase summary when confirmed */}
            {phasesConfirmed && phases.length > 0 && (
              <div className="shrink-0 px-4 py-3 flex items-center gap-3 overflow-x-auto" style={{ background: 'var(--color-navy-light)', borderBottom: '1px solid var(--color-border)' }}>
                <span className="text-[10px] uppercase tracking-wider shrink-0" style={{ color: 'var(--color-text-dim)' }}>Phases:</span>
                {phases.map((p, i) => (
                  <div key={i} className="flex items-center gap-1.5 shrink-0">
                    {i > 0 && <span style={{ color: 'var(--color-border)' }}>→</span>}
                    <div className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px]" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-teal-dim)' }}>
                      <span className="w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>{p.number}</span>
                      <span style={{ color: 'var(--color-text)' }}>{p.name}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Agent suggestion loading */}
            {phasesConfirmed && suggestingAgents && (
              <div className="flex items-center justify-center py-8">
                <div className="text-sm animate-pulse" style={{ color: 'var(--color-teal-dim)' }}>
                  {mode === 'stress_test' ? 'Suggesting review agents based on your documents and phases...' : 'Suggesting agents based on your problem and phases...'}
                </div>
              </div>
            )}

            <div className="flex-1 min-h-0">
              <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={handleNodeClick} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
                <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e2438" />
              </ReactFlow>
            </div>
          </div>
        )}
      </div>
      <AgentLibrary />
      <AgentDrawer />

      {/* Pre-run confirmation modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <div className="w-full max-w-lg max-h-[80vh] overflow-y-auto p-6 rounded-xl" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-border)' }}>
            <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--color-teal)' }}>Confirm Symposium</h2>

            <div className="mb-4">
              <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--color-text-dim)' }}>Problem Statement</p>
              <p className="text-sm p-3 rounded-lg whitespace-pre-wrap" style={{ background: 'var(--color-navy)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}>{problemStatement}</p>
            </div>

            <div className="mb-4">
              <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--color-text-dim)' }}>Mode</p>
              <p className="text-sm" style={{ color: 'var(--color-text)' }}>{mode === 'product' ? 'Product Discussion' : mode === 'stress_test' ? 'Stress Test' : 'Problem Discussion'}</p>
            </div>

            <div className="mb-4">
              <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--color-text-dim)' }}>Agents ({nodes.length})</p>
              <div className="space-y-2">
                {nodes.map((n) => (
                  <div key={n.id} className="flex items-center gap-2 p-2 rounded-lg text-xs" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)' }}>
                    <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0" style={{ background: 'var(--color-navy-lighter)', border: '1px solid var(--color-border)' }}>
                      <span className="text-[10px] font-bold" style={{ color: 'var(--color-teal)' }}>{n.data.name?.charAt(0)}</span>
                    </div>
                    <div className="min-w-0">
                      <span className="font-medium" style={{ color: 'var(--color-text)' }}>{n.data.name?.replace(/_/g, ' ')}</span>
                      {n.data.role_tag && <span className="ml-2 text-[10px]" style={{ color: 'var(--color-teal-dim)' }}>{n.data.role_tag}</span>}
                      {!n.data.persona && <span className="ml-2 text-[10px]" style={{ color: '#f87171' }}>No persona</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mb-6">
              <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--color-text-dim)' }}>Settings</p>
              <div className="flex gap-4 text-xs" style={{ color: 'var(--color-text-dim)' }}>
                <span>{settings.max_rounds} rounds</span>
                <span>Temp {settings.temperature}</span>
                <span>Gate @ round {settings.gate_start_round}</span>
              </div>
            </div>

            {/* PRD Panel Selection (Product mode only) */}
            {mode === 'product' && (
              <div className="mb-4">
                <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--color-text-dim)' }}>
                  PRD Panel Agents {loadingPrdSuggest && <span className="animate-pulse ml-1">(AI suggesting...)</span>}
                </p>
                <p className="text-[10px] mb-2" style={{ color: 'var(--color-text-dim)' }}>
                  These agents will co-author the PRD after the brainstorm. Click to toggle.
                </p>
                <div className="space-y-1.5">
                  {nodes.map((n) => {
                    const isSelected = prdPanelNames.includes(n.data.name);
                    const isProduct = n.data.name === prdProductAgent;
                    return (
                      <button
                        key={n.id}
                        onClick={() => {
                          if (isProduct) return; // Can't deselect mandatory product agent
                          setPrdPanelNames((prev) =>
                            isSelected ? prev.filter((name) => name !== n.data.name) : [...prev, n.data.name]
                          );
                        }}
                        className="w-full flex items-center gap-2 p-2 rounded-lg text-xs text-left"
                        style={{
                          background: isSelected ? 'var(--color-navy)' : 'transparent',
                          border: `1px solid ${isSelected ? 'var(--color-teal-dim)' : 'var(--color-border)'}`,
                          opacity: isProduct ? 1 : undefined,
                        }}
                      >
                        <div
                          className="w-4 h-4 rounded flex items-center justify-center shrink-0"
                          style={{
                            background: isSelected ? 'var(--color-teal)' : 'transparent',
                            border: `1px solid ${isSelected ? 'var(--color-teal)' : 'var(--color-border)'}`,
                          }}
                        >
                          {isSelected && <span className="text-[9px] font-bold" style={{ color: 'var(--color-navy)' }}>✓</span>}
                        </div>
                        <span style={{ color: 'var(--color-text)' }}>{n.data.name?.replace(/_/g, ' ')}</span>
                        {n.data.role_tag && <span className="text-[10px]" style={{ color: 'var(--color-teal-dim)' }}>{n.data.role_tag}</span>}
                        {isProduct && <span className="text-[9px] px-1.5 py-0.5 rounded ml-auto" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>Product Lead</span>}
                        {prdRationale[n.data.name] && isSelected && !isProduct && (
                          <span className="text-[9px] ml-auto" style={{ color: 'var(--color-text-dim)' }}>{prdRationale[n.data.name]}</span>
                        )}
                      </button>
                    );
                  })}
                </div>
                {prdPanelNames.length < 2 && (
                  <p className="text-[10px] mt-1" style={{ color: '#fbbf24' }}>Select at least 2 agents for the PRD panel</p>
                )}
              </div>
            )}

            {/* Warnings */}
            {nodes.some((n) => !n.data.persona) && (
              <div className="mb-4 p-2 rounded-lg text-xs" style={{ background: '#1a0a0a', border: '1px solid #7f1d1d', color: '#f87171' }}>
                Some agents have no persona defined. They may produce generic responses.
              </div>
            )}

            <div className="flex gap-3">
              <button onClick={() => setShowConfirm(false)} className="flex-1 py-2.5 rounded-lg text-sm" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>Go Back</button>
              <button onClick={handleConfirmStart} disabled={mode === 'product' && prdPanelNames.length < 2} className="flex-1 py-2.5 rounded-lg text-sm font-bold disabled:opacity-40" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>Start Session</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

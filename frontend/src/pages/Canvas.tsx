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
import LiveFeed from '../components/session/LiveFeed';
import ArtifactPanel from '../components/session/ArtifactPanel';
import StatsBar from '../components/session/StatsBar';

const nodeTypes = { agentNode: AgentNode };

const defaultSettings: SessionSettings = {
  max_rounds: 50,
  temperature: 0.70,
  gate_start_round: 10,
  overseer_interval: 10,
  min_rounds_before_convergence: 45,
  prd_panel_rounds: 10,
};

export default function Canvas() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentSession, fetchSession, updateSession } = useSessionStore();
  const { nodes, edges, onNodesChange, onEdgesChange, selectNode, addAgent } = useCanvasStore();

  const [problemStatement, setProblemStatement] = useState('');
  const [mode, setMode] = useState('product');
  const [settings, setSettings] = useState<SessionSettings>(defaultSettings);
  const [isLive, setIsLive] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const { connect, connected: _connected, messages: wsMessages } = useWebSocket({
    sessionId: id || '',
    onMessage: (msg) => {
      if (msg.type === 'agent_message' && !msg.streaming) {
        useCanvasStore.getState().setActiveAgent(msg.source as string);
      }
      if (msg.type === 'session_complete') {
        useCanvasStore.getState().setActiveAgent(null);
        setTimeout(() => navigate(`/results/${id}`), 2000);
      }
    },
  });

  useEffect(() => {
    if (id) fetchSession(id);
  }, [id, fetchSession]);

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
      setLoaded(true);
    }
  }, [currentSession, loaded, addAgent]);

  const handleSave = useCallback(async () => {
    if (!id) return;
    const agentConfigs = nodes.map((n: Node<AgentNodeData>) => ({
      id: n.id, name: n.data.name, model: n.data.model, persona: n.data.persona,
      tools: n.data.tools, role_tag: n.data.role_tag, canvas_position: n.position,
    }));
    await updateSession(id, {
      problem_statement: problemStatement,
      mode: mode as SessionSettings['temperature'] extends number ? 'product' | 'problem' : never,
      agents: agentConfigs as any,
      settings,
    });
  }, [id, nodes, problemStatement, mode, settings, updateSession]);

  const handleBeginSymposium = async () => {
    await handleSave();
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
      <div className="h-screen flex flex-col" style={{ background: 'var(--color-navy)' }}>
        <StatsBar messages={wsMessages} maxRounds={settings.max_rounds} />
        <div className="flex-1 flex">
          <div className="w-2/5 h-full" style={{ borderRight: '1px solid var(--color-border)' }}>
            <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e2438" />
            </ReactFlow>
          </div>
          <div className="w-3/5 h-full flex flex-col">
            <LiveFeed messages={wsMessages} />
            <div style={{ height: '30%', borderTop: '1px solid var(--color-border)' }}>
              <ArtifactPanel messages={wsMessages} />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex" style={{ background: 'var(--color-navy)' }}>
      <div className="w-80 h-full overflow-y-auto p-4 flex flex-col gap-4" style={{ background: 'var(--color-navy-light)', borderRight: '1px solid var(--color-border)' }}>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold" style={{ color: 'var(--color-teal)' }}>Setup</h2>
          <button onClick={() => navigate('/sessions')} className="text-xs" style={{ color: 'var(--color-text-dim)' }}>Back</button>
        </div>
        <ProblemStatement value={problemStatement} onChange={setProblemStatement} />
        <ModeSelector value={mode} onChange={setMode} />
        <AdvancedSettings settings={settings} onChange={setSettings} />
        <button onClick={handleSave} className="w-full py-2 rounded-lg text-sm" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>Save Draft</button>
        <button onClick={handleBeginSymposium} disabled={!problemStatement || nodes.length < 2} className="w-full py-3 rounded-lg font-bold text-sm transition-colors disabled:opacity-40" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>Begin Symposium</button>
        {nodes.length < 2 && (<p className="text-[10px]" style={{ color: '#fbbf24' }}>Add at least 2 agents to begin</p>)}
      </div>
      <div className="flex-1 h-full">
        <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={handleNodeClick} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e2438" />
        </ReactFlow>
      </div>
      <AgentLibrary />
      <AgentDrawer />
    </div>
  );
}

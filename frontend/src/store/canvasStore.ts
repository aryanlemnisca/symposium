import { create } from 'zustand';
import { Node, Edge, applyNodeChanges, applyEdgeChanges, NodeChange, EdgeChange } from '@xyflow/react';

export interface AgentNodeData {
  id: string;
  name: string;
  model: string;
  persona: string;
  tools: string[];
  role_tag: string | null;
  isActive?: boolean;
  [key: string]: unknown;
}

interface CanvasState {
  nodes: Node<AgentNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  drawerOpen: boolean;

  setNodes: (nodes: Node<AgentNodeData>[]) => void;
  setEdges: (edges: Edge[]) => void;
  onNodesChange: (changes: NodeChange<Node<AgentNodeData>>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;

  addAgent: (agent: AgentNodeData, position: { x: number; y: number }) => void;
  removeAgent: (nodeId: string) => void;
  updateAgent: (nodeId: string, data: Partial<AgentNodeData>) => void;
  setActiveAgent: (agentName: string | null) => void;

  selectNode: (nodeId: string | null) => void;
  setDrawerOpen: (open: boolean) => void;

  rebuildEdges: () => void;
}

let nodeIdCounter = 0;

export const useCanvasStore = create<CanvasState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  drawerOpen: false,

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  onNodesChange: (changes) => {
    set({ nodes: applyNodeChanges(changes, get().nodes) });
  },
  onEdgesChange: (changes) => {
    set({ edges: applyEdgeChanges(changes, get().edges) });
  },

  addAgent: (agent, position) => {
    const nodeId = `agent-${++nodeIdCounter}`;
    const newNode: Node<AgentNodeData> = {
      id: nodeId,
      type: 'agentNode',
      position,
      data: { ...agent, id: nodeId },
    };
    set((s) => ({ nodes: [...s.nodes, newNode] }));
    get().rebuildEdges();
  },

  removeAgent: (nodeId) => {
    set((s) => ({ nodes: s.nodes.filter((n) => n.id !== nodeId) }));
    get().rebuildEdges();
  },

  updateAgent: (nodeId, data) => {
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n
      ),
    }));
  },

  setActiveAgent: (agentName) => {
    set((s) => ({
      nodes: s.nodes.map((n) => ({
        ...n,
        data: { ...n.data, isActive: n.data.name === agentName },
      })),
    }));
  },

  selectNode: (nodeId) => {
    set({ selectedNodeId: nodeId, drawerOpen: !!nodeId });
  },

  setDrawerOpen: (open) => set({ drawerOpen: open }),

  rebuildEdges: () => {
    const { nodes } = get();
    const edges: Edge[] = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        edges.push({
          id: `e-${nodes[i].id}-${nodes[j].id}`,
          source: nodes[i].id,
          target: nodes[j].id,
          style: { stroke: '#2a3050', strokeWidth: 1 },
          animated: false,
        });
      }
    }
    set({ edges });
  },
}));

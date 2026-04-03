import { create } from 'zustand';
import { applyNodeChanges, applyEdgeChanges, type Node, type Edge, type NodeChange, type EdgeChange } from '@xyflow/react';

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
  reset: () => void;
}

let nodeIdCounter = 0;

const CIRCLE_RADIUS = 200;
const CIRCLE_CENTER = { x: 350, y: 300 };

function arrangeCircle(nodes: Node<AgentNodeData>[]): Node<AgentNodeData>[] {
  if (nodes.length === 0) return nodes;
  if (nodes.length === 1) {
    return [{ ...nodes[0], position: CIRCLE_CENTER }];
  }
  return nodes.map((node, i) => {
    const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
    return {
      ...node,
      position: {
        x: CIRCLE_CENTER.x + CIRCLE_RADIUS * Math.cos(angle),
        y: CIRCLE_CENTER.y + CIRCLE_RADIUS * Math.sin(angle),
      },
    };
  });
}

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
    set((s) => {
      const newNodes = [...s.nodes, newNode];
      return { nodes: arrangeCircle(newNodes), edges: [] };
    });
  },

  removeAgent: (nodeId) => {
    set((s) => {
      const newNodes = s.nodes.filter((n) => n.id !== nodeId);
      return { nodes: arrangeCircle(newNodes), edges: [] };
    });
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
    set({ edges: [] });
  },

  reset: () => {
    nodeIdCounter = 0;
    set({ nodes: [], edges: [], selectedNodeId: null, drawerOpen: false });
  },
}));

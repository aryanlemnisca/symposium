import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { useCanvasStore, type AgentNodeData } from '../../store/canvasStore';

type AgentNodeType = Node<AgentNodeData>;

function AgentNode({ data, id }: NodeProps<AgentNodeType>) {
  const isActive = data.isActive;
  const removeAgent = useCanvasStore((s) => s.removeAgent);

  return (
    <div className="flex flex-col items-center group">
      <Handle type="target" position={Position.Top} style={{ visibility: 'hidden' }} />

      <div className="relative">
        <div
          className="relative w-20 h-20 rounded-full flex items-center justify-center cursor-pointer transition-all"
          style={{
            background: 'var(--color-navy-lighter)',
            border: `2px solid ${isActive ? 'var(--color-teal)' : 'var(--color-border)'}`,
            boxShadow: isActive ? '0 0 20px rgba(45, 212, 191, 0.4)' : 'none',
          }}
        >
          {isActive && (
            <div
              className="absolute inset-0 rounded-full animate-ping"
              style={{
                border: '2px solid var(--color-teal)',
                opacity: 0.3,
              }}
            />
          )}
          <span className="text-lg font-bold" style={{ color: 'var(--color-teal)' }}>
            {data.name?.charAt(0) || '?'}
          </span>
        </div>

        {/* Web search indicator */}
        {(data.tools || []).includes('web_search') && (
          <div
            className="absolute -bottom-0.5 -right-0.5 w-5 h-5 rounded-full flex items-center justify-center text-[10px]"
            style={{ background: 'var(--color-navy-lighter)', border: '1px solid var(--color-teal)', color: 'var(--color-teal)' }}
            title="Web search enabled"
          >
            W
          </div>
        )}

        {/* Delete button — visible on hover */}
        <button
          onClick={(e) => { e.stopPropagation(); removeAgent(id); }}
          className="absolute -top-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ background: '#7f1d1d', color: '#f87171', fontSize: '10px', lineHeight: 1 }}
        >
          x
        </button>
      </div>

      <p className="mt-2 text-xs font-medium text-center max-w-24 truncate" style={{ color: 'var(--color-text)' }}>
        {data.name || 'Unnamed'}
      </p>

      {data.role_tag && (
        <span
          className="mt-1 text-[10px] px-2 py-0.5 rounded-full"
          style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}
        >
          {data.role_tag}
        </span>
      )}

      <Handle type="source" position={Position.Bottom} style={{ visibility: 'hidden' }} />
    </div>
  );
}

export default memo(AgentNode);

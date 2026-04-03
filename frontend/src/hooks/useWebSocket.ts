import { useEffect, useRef, useState, useCallback } from 'react';

export interface WSMessage {
  type: string;
  [key: string]: unknown;
}

interface UseWebSocketOptions {
  sessionId: string;
  apiKey?: string;
  onMessage?: (msg: WSMessage) => void;
}

export function useWebSocket({ sessionId, apiKey, onMessage }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<WSMessage[]>([]);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/sessions/${sessionId}/ws`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      if (apiKey) {
        ws.send(JSON.stringify({ api_key: apiKey }));
      } else {
        ws.send(JSON.stringify({}));
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);

        if (msg.type === 'agent_message_chunk') {
          // Update the last streaming message in-place
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.type === 'agent_message' && last.streaming && last.source === msg.source) {
              const updated = { ...last, content: msg.content };
              return [...prev.slice(0, -1), updated];
            }
            return prev;
          });
        } else if (msg.type === 'agent_message' && !msg.streaming) {
          // Final message replaces the streaming placeholder
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.type === 'agent_message' && last.streaming && last.source === msg.source) {
              return [...prev.slice(0, -1), msg];
            }
            return [...prev, msg];
          });
        } else {
          setMessages((prev) => [...prev, msg]);
        }

        onMessage?.(msg);
      } catch {}
    };

    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
  }, [sessionId, apiKey, onMessage]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
  }, []);

  const sendCommand = useCallback((action: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action }));
    }
  }, []);

  useEffect(() => {
    return () => { wsRef.current?.close(); };
  }, []);

  return { connect, disconnect, connected, messages, sendCommand };
}

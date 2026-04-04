"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { WSChannel, WSMessage } from "@/lib/types";

const WS_URL = `ws://${typeof window !== "undefined" ? window.location.hostname : "localhost"}:8400/ws`;
const PING_INTERVAL_MS = 30_000;
const MAX_BACKOFF_MS = 16_000;

export function useWebSocket(channels: WSChannel[]): {
  lastMessage: WSMessage | null;
  isConnected: boolean;
  channelData: Record<WSChannel, unknown>;
} {
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [channelData, setChannelData] = useState<Record<WSChannel, unknown>>({
    signals: null,
    regime: null,
    broker: null,
    health: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);
  const channelsRef = useRef(channels);
  channelsRef.current = channels;

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.addEventListener("open", () => {
      if (!mountedRef.current) {
        ws.close();
        return;
      }
      backoffRef.current = 1000;
      setIsConnected(true);
      for (const ch of channelsRef.current) {
        ws.send(JSON.stringify({ type: "subscribe", channel: ch }));
      }
      pingTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, PING_INTERVAL_MS);
    });

    ws.addEventListener("message", (event: MessageEvent) => {
      if (!mountedRef.current) return;
      let msg: WSMessage;
      try {
        msg = JSON.parse(event.data as string) as WSMessage;
      } catch {
        return;
      }
      setLastMessage(msg);
      if (msg.type === "push" && msg.channel !== undefined) {
        const ch = msg.channel;
        setChannelData((prev) => ({ ...prev, [ch]: msg.data }));
      }
    });

    ws.addEventListener("close", () => {
      if (!mountedRef.current) return;
      setIsConnected(false);
      if (pingTimerRef.current !== null) {
        clearInterval(pingTimerRef.current);
        pingTimerRef.current = null;
      }
      const delay = backoffRef.current;
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      reconnectTimerRef.current = setTimeout(connect, delay);
    });

    ws.addEventListener("error", () => {
      ws.close();
    });
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (pingTimerRef.current !== null) {
        clearInterval(pingTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  return { lastMessage, isConnected, channelData };
}

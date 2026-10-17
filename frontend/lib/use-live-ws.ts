"use client";

import { useEffect, useState } from "react";
import type { LiveHTMatch } from "./api";

function getWsUrl(): string {
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const publicUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "");
  if (publicUrl) {
    const url = new URL(publicUrl);
    return `${url.protocol === "https:" ? "wss:" : "ws:"}//${url.host}/ws/live-ht`;
  }
  return `${proto}//${window.location.host}/ws/live-ht`;
}

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 15000];
const PING_INTERVAL = 30_000;
/** REST'e düştükten sonra WS'ye sessizce yeniden bağlanma denemesi aralığı. */
export const FALLBACK_RETRY_MS = 60_000;

export type WsStatus = "connecting" | "connected" | "disconnected" | "fallback";

export interface UseLiveWsResult {
  matches: LiveHTMatch[];
  status: WsStatus;
  lastUpdate: Date | null;
}

function isMatchList(value: unknown): value is LiveHTMatch[] {
  return Array.isArray(value) && value.every((item) =>
    item !== null && typeof item === "object" && typeof (item as LiveHTMatch).match_id === "string",
  );
}

export function useLiveWs(): UseLiveWsResult {
  const [matches, setMatches] = useState<LiveHTMatch[]>([]);
  const [status, setStatus] = useState<WsStatus>("connecting");
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retryCount = 0;
    let pingTimer: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;

    const clearTimers = () => {
      if (pingTimer) clearInterval(pingTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      pingTimer = null;
      reconnectTimer = null;
    };

    const closeSocket = () => {
      if (!ws) return;
      ws.onopen = ws.onmessage = ws.onerror = ws.onclose = null;
      if (ws.readyState <= WebSocket.OPEN) ws.close();
      ws = null;
    };

    // quiet: fallback'teyken yeniden deneme — durum "fallback" kalır, REST akışı bozulmaz.
    const connect = (quiet: boolean) => {
      if (disposed) return;
      clearTimers();
      closeSocket();
      const url = getWsUrl();
      if (!url) {
        setStatus("fallback");
        return;
      }
      if (!quiet) setStatus("connecting");
      try {
        const socket = new WebSocket(url);
        ws = socket;
        socket.onopen = () => {
          if (disposed) return;
          retryCount = 0;
          setStatus("connected");
          pingTimer = setInterval(() => {
            if (socket.readyState === WebSocket.OPEN) socket.send("ping");
          }, PING_INTERVAL);
        };
        socket.onmessage = (event) => {
          if (disposed || event.data === "pong") return;
          try {
            const data: unknown = JSON.parse(event.data);
            if (!isMatchList(data)) return;
            setMatches(data);
            setLastUpdate(new Date());
          } catch {
            // bozuk mesaj — yoksay
          }
        };
        socket.onclose = () => {
          if (disposed) return;
          if (pingTimer) clearInterval(pingTimer);
          pingTimer = null;
          retryCount++;
          if (retryCount > RECONNECT_DELAYS.length) {
            setStatus("fallback");
            retryCount = RECONNECT_DELAYS.length;
            reconnectTimer = setTimeout(() => connect(true), FALLBACK_RETRY_MS);
            return;
          }
          setStatus("disconnected");
          reconnectTimer = setTimeout(() => connect(false), RECONNECT_DELAYS[retryCount - 1]);
        };
      } catch {
        setStatus("fallback");
        reconnectTimer = setTimeout(() => connect(true), FALLBACK_RETRY_MS);
      }
    };

    connect(false);
    return () => {
      disposed = true;
      clearTimers();
      closeSocket();
    };
  }, []);

  return { matches, status, lastUpdate };
}

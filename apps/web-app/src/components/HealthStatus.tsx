"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
import { HealthResponse } from "@/lib/types";
import { CheckCircle, AlertCircle, Loader2 } from "lucide-react";

export function HealthStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        setLoading(true);
        const data = await getHealth();
        setHealth(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Health check failed");
        setHealth(null);
      } finally {
        setLoading(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30s

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-sm">Checking...</span>
      </div>
    );
  }

  if (error || !health) {
    return (
      <div className="flex items-center gap-2 text-red-600">
        <AlertCircle className="w-4 h-4" />
        <span className="text-sm font-medium">Offline</span>
      </div>
    );
  }

  const isHealthy = health.status === "ok";

  return (
    <div className={`flex items-center gap-2 ${isHealthy ? "text-green-600" : "text-yellow-600"}`}>
      <CheckCircle className="w-4 h-4" />
      <span className="text-sm font-medium">
        Online {health.version && `(v${health.version})`}
      </span>
    </div>
  );
}

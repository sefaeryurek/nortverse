import AnalyzeClient from "./AnalyzeClient";
import { analyzeMatch } from "@/lib/api";
import type { AnalyzeResponse } from "@/lib/types";

interface Props {
  params: Promise<{ match_id: string }>;
  searchParams: Promise<{ home?: string | string[]; away?: string | string[] }>;
}

export default async function AnalyzePage({ params, searchParams }: Props) {
  const [{ match_id }, query] = await Promise.all([params, searchParams]);
  let data: AnalyzeResponse | null = null;
  let error = "";
  try {
    data = await analyzeMatch(match_id);
  } catch (cause) {
    error = cause instanceof Error ? cause.message : "Analiz yüklenemedi. Lütfen yeniden deneyin.";
  }

  return (
    <AnalyzeClient
      key={match_id}
      match_id={match_id}
      initialData={data}
      initialError={error}
      urlHome={typeof query.home === "string" ? query.home : ""}
      urlAway={typeof query.away === "string" ? query.away : ""}
    />
  );
}

import AnalyzeClient from "./AnalyzeClient";
import { analyzeMatch, getAnalysisEvidence } from "@/lib/api";
import type { AnalysisEvidence, AnalyzeResponse } from "@/lib/types";

interface Props {
  params: Promise<{ match_id: string }>;
  searchParams: Promise<{ home?: string | string[]; away?: string | string[] }>;
}

export default async function AnalyzePage({ params, searchParams }: Props) {
  const [{ match_id }, query] = await Promise.all([params, searchParams]);
  let data: AnalyzeResponse | null = null;
  let evidence: AnalysisEvidence | null = null;
  let error = "";
  const [analysisResult, evidenceResult] = await Promise.allSettled([
    analyzeMatch(match_id), getAnalysisEvidence(),
  ]);
  if (analysisResult.status === "fulfilled") data = analysisResult.value;
  else error = analysisResult.reason instanceof Error
    ? analysisResult.reason.message : "Analiz yüklenemedi. Lütfen yeniden deneyin.";
  if (evidenceResult.status === "fulfilled") evidence = evidenceResult.value;

  return (
    <AnalyzeClient
      key={match_id}
      match_id={match_id}
      initialData={data}
      evidence={evidence}
      initialError={error}
      urlHome={typeof query.home === "string" ? query.home : ""}
      urlAway={typeof query.away === "string" ? query.away : ""}
    />
  );
}

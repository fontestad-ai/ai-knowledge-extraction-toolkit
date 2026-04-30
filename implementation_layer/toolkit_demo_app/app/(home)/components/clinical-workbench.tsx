"use client";

import { FileUpload } from "@/components/demo/file-upload";
import {
  EmptyStateCard,
  LoadingCard,
  ResultCard,
  ResultJson,
  ResultText,
} from "@/components/demo/result-card";
import { apiFetch, RateLimitError } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Activity,
  BrainCircuit,
  FileJson2,
  HeartPulse,
  Loader2,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";

const DEFAULT_REQUIREMENTS = `Extract only source-grounded, clinically actionable hypertension guideline knowledge.
Capture diagnostic blood-pressure thresholds, staging/categories, treatment thresholds,
lifestyle recommendations, medication recommendations, contraindications, follow-up intervals,
target populations, recommendation strength, evidence grade, and exceptions.
Every actionable item must include source_file, page_number when available, section_heading when available,
and a verbatim source_quote. Never infer missing values; use null or an empty list and record uncertainty
in source_gaps_or_uncertainties.`;

interface ClinicalExampleAsset {
  name: string;
  url: string;
  media_type: string;
}

interface ClinicalExtractResult {
  run_id: string;
  source_file: string;
  parser_choice: string;
  extraction_backend: string;
  route: Record<string, unknown> | null;
  parsed_documents: string[];
  extracted_knowledge: Record<string, unknown>[];
  operationalized_knowledge: Record<string, unknown> | null;
  validation: Record<string, unknown> | null;
  quality_report: Record<string, unknown> | null;
  persistence: Record<string, unknown>;
}

const PARSER_OPTIONS = [
  { value: "auto", label: "Auto" },
  { value: "pdf_text", label: "Local PDF text" },
  { value: "pptx_text", label: "Local PowerPoint text" },
  { value: "local_image", label: "Local image artifact registry" },
  { value: "pymupdf", label: "PyMuPDF" },
  { value: "docling", label: "Docling" },
  { value: "docx", label: "DOCX" },
] as const;

export function ClinicalWorkbench() {
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [examples, setExamples] = useState<ClinicalExampleAsset[]>([]);
  const [selectedExample, setSelectedExample] = useState<string>("__none__");
  const [userRequirements, setUserRequirements] =
    useState(DEFAULT_REQUIREMENTS);
  const [parserChoice, setParserChoice] = useState<string>("auto");
  const [operationalize, setOperationalize] = useState(true);
  const [validateExtraction, setValidateExtraction] = useState(false);
  const [isLoadingExamples, setIsLoadingExamples] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ClinicalExtractResult | null>(null);

  useEffect(() => {
    let ignore = false;

    async function loadExamples(): Promise<void> {
      try {
        const response = await fetch("/api/clinical/examples");
        if (!response.ok) {
          throw new Error("Failed to load bundled example assets");
        }
        const data = (await response.json()) as { examples: ClinicalExampleAsset[] };
        if (!ignore) {
          setExamples(data.examples);
        }
      } catch (error) {
        if (!ignore) {
          toast.error(
            error instanceof Error ? error.message : "Failed to load examples",
          );
        }
      } finally {
        if (!ignore) {
          setIsLoadingExamples(false);
        }
      }
    }

    void loadExamples();
    return () => {
      ignore = true;
    };
  }, []);

  const summary = useMemo(() => {
    const firstPayload = result?.extracted_knowledge?.[0] ?? {};
    const operationalized = (
      result?.operationalized_knowledge as { atomic_units?: unknown[] } | null
    )?.atomic_units?.length;

    return {
      thresholdCount: Array.isArray(
        (firstPayload as { bp_thresholds?: unknown[] }).bp_thresholds,
      )
        ? ((firstPayload as { bp_thresholds?: unknown[] }).bp_thresholds
            ?.length ?? 0)
        : 0,
      treatmentCount: Array.isArray(
        (firstPayload as { treatment_recommendations?: unknown[] })
          .treatment_recommendations,
      )
        ? ((firstPayload as { treatment_recommendations?: unknown[] })
            .treatment_recommendations?.length ?? 0)
        : 0,
      atomicUnitCount: operationalized ?? 0,
    };
  }, [result]);

  async function handleUseExample(name: string): Promise<void> {
    if (name === "__none__") {
      setSelectedExample(name);
      return;
    }

    const example = examples.find((item) => item.name === name);
    if (!example) return;

    try {
      const response = await fetch(example.url);
      if (!response.ok) {
        throw new Error("Failed to load example asset");
      }
      const blob = await response.blob();
      const file = new File([blob], example.name, {
        type: blob.type || example.media_type,
      });
      setDocumentFile(file);
      setSelectedExample(name);
      setResult(null);
      toast.success(`Loaded example: ${example.name}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load example");
    }
  }

  async function handleSubmit(): Promise<void> {
    if (!documentFile || isLoading) return;

    setIsLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", documentFile);
      formData.append("user_requirements", userRequirements);
      formData.append("parser_choice", parserChoice);
      formData.append("operationalize", String(operationalize));
      formData.append("validate_extraction", String(validateExtraction));

      const response = await apiFetch("/api/clinical/extract", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = (await response.json().catch(() => null)) as
          | { detail?: string }
          | null;
        throw new Error(error?.detail || "Clinical extraction failed");
      }

      const data = (await response.json()) as ClinicalExtractResult;
      setResult(data);
      toast.success("Clinical knowledge extracted successfully");
    } catch (error) {
      if (error instanceof RateLimitError) return;
      toast.error(
        error instanceof Error ? error.message : "Clinical extraction failed",
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <div className="text-primary inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium">
          <HeartPulse className="h-4 w-4" />
          Current frontend UI, clinical-only workflow
        </div>
        <div className="space-y-3">
          <h1 className="font-serif text-4xl font-semibold tracking-tight sm:text-5xl">
            Clinical Knowledge Extraction
          </h1>
          <p className="text-muted-foreground max-w-3xl text-base sm:text-lg">
            Upload a guideline PDF, PowerPoint, Word file, or page image,
            extract source-grounded clinical knowledge through LMCLI-first local
            extraction, persist the run in SQLite, and review artifacts for
            downstream records, retrieval, and graph workflows.
          </p>
        </div>
      </section>

      <Card className="border-dashed">
        <CardHeader>
          <CardTitle>Runtime dependency surface</CardTitle>
          <CardDescription>
            External services removed from the frontend shell and the remaining
            dependency posture after moving the active clinical extraction path
            away from OpenAI/Azure calls.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <h2 className="font-medium">Removed now</h2>
            <ul className="text-muted-foreground list-disc space-y-1 pl-5 text-sm">
              <li>Supabase auth and access control</li>
              <li>Upstash Redis rate limiting</li>
              <li>PostHog analytics and remote widget bootstraps</li>
            </ul>
          </div>
          <div className="space-y-2">
            <h2 className="font-medium">Local-first target</h2>
            <ul className="text-muted-foreground list-disc space-y-1 pl-5 text-sm">
              <li>SQLite stores extraction runs and operationalized clinical units</li>
              <li>RAG rows are sqlite-vec-ready with local embedding slots</li>
              <li>No active auth database in this branch</li>
            </ul>
          </div>
          <div className="space-y-2">
            <h2 className="font-medium">Still external today</h2>
            <ul className="text-muted-foreground list-disc space-y-1 pl-5 text-sm">
              <li>Active clinical extraction uses LMCLI when configured</li>
              <li>When LMCLI is absent, a conservative local deterministic extractor runs</li>
              <li>OpenAI/Azure remain in broader toolkit dependencies but are not called by this path</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Guideline input</CardTitle>
              <CardDescription>
                Upload a PDF, PowerPoint, Word document, or page image from the
                clinical guideline source.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <FileUpload
                accept=".pdf,.ppt,.pptx,.doc,.docx,.png,.jpg,.jpeg"
                maxSize={20}
                file={documentFile}
                onFileSelect={setDocumentFile}
                onFileRemove={() => {
                  setDocumentFile(null);
                  setSelectedExample("__none__");
                  setResult(null);
                }}
                disabled={isLoading}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Bundled example assets</CardTitle>
              <CardDescription>
                Load one of the uploaded guideline files from the repository
                uploads folder for manual testing.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Label htmlFor="example-asset">Uploaded example</Label>
              <Select
                value={selectedExample}
                onValueChange={(value) => void handleUseExample(value)}
                disabled={isLoadingExamples || isLoading || examples.length === 0}
              >
                <SelectTrigger id="example-asset">
                  <SelectValue
                    placeholder={
                      isLoadingExamples
                        ? "Loading examples..."
                        : examples.length === 0
                          ? "No bundled examples found"
                          : "Select an uploaded example"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">None</SelectItem>
                  {examples.map((example) => (
                    <SelectItem key={example.name} value={example.name}>
                      {example.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-muted-foreground text-sm">
                The uploaded hypertension guideline images remain available from
                the branch-level <code>uploads/</code> folder.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Extraction settings</CardTitle>
              <CardDescription>
                Keep the default clinical requirements, or tailor them to the
                exact evidence you want to capture.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="clinical-requirements">Clinical requirements</Label>
                <Textarea
                  id="clinical-requirements"
                  value={userRequirements}
                  onChange={(event) => setUserRequirements(event.target.value)}
                  rows={8}
                  disabled={isLoading}
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="parser-choice">Parser</Label>
                  <Select
                    value={parserChoice}
                    onValueChange={setParserChoice}
                    disabled={isLoading}
                  >
                    <SelectTrigger id="parser-choice">
                      <SelectValue placeholder="Select parser" />
                    </SelectTrigger>
                    <SelectContent>
                      {PARSER_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-3 rounded-lg border p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <Label htmlFor="operationalize">Operationalize output</Label>
                      <p className="text-muted-foreground text-sm">
                        Build atomic units, retrieval documents, and graph-ready
                        projections.
                      </p>
                    </div>
                    <Switch
                      id="operationalize"
                      checked={operationalize}
                      onCheckedChange={setOperationalize}
                      disabled={isLoading}
                    />
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <Label htmlFor="validate-extraction">Validate extraction</Label>
                      <p className="text-muted-foreground text-sm">
                        Uses rendered PDF pages or source images when validator
                        extras are available.
                      </p>
                    </div>
                    <Switch
                      id="validate-extraction"
                      checked={validateExtraction}
                      onCheckedChange={setValidateExtraction}
                      disabled={isLoading}
                    />
                  </div>
                </div>
              </div>

              <Button
                onClick={() => void handleSubmit()}
                disabled={!documentFile || isLoading}
                className="w-full gap-2"
                size="lg"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Extracting clinical knowledge
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Run clinical extraction
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          {isLoading ? (
            <LoadingCard
              message="Extracting clinical knowledge..."
              subMessage="Parsing the source, generating structured guideline output, and preparing traceable clinical artifacts."
            />
          ) : result ? (
            <>
              <div className="grid gap-4 md:grid-cols-3">
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>BP thresholds</CardDescription>
                    <CardTitle className="text-2xl">{summary.thresholdCount}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-muted-foreground flex items-center gap-2 text-sm">
                      <Activity className="h-4 w-4" />
                      Threshold items extracted
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Treatment recommendations</CardDescription>
                    <CardTitle className="text-2xl">{summary.treatmentCount}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-muted-foreground flex items-center gap-2 text-sm">
                      <BrainCircuit className="h-4 w-4" />
                      Actionable recommendations captured
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Atomic units</CardDescription>
                    <CardTitle className="text-2xl">{summary.atomicUnitCount}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-muted-foreground flex items-center gap-2 text-sm">
                      <FileJson2 className="h-4 w-4" />
                      Operationalized clinical units
                    </div>
                  </CardContent>
                </Card>
              </div>

              <ResultCard
                title="Extracted clinical knowledge"
                description={`Run: ${result.run_id} · Source: ${result.source_file} · Parser: ${result.parser_choice} · Backend: ${result.extraction_backend}`}
                copyContent={JSON.stringify(result.extracted_knowledge, null, 2)}
              >
                <ResultJson data={result.extracted_knowledge} maxHeight="360px" />
              </ResultCard>

              {result.quality_report && (
                <ResultCard
                  title="Quality control report"
                  description="Acceptance status, issues, and mitigations applied during local extraction."
                  copyContent={JSON.stringify(result.quality_report, null, 2)}
                >
                  <ResultJson data={result.quality_report} maxHeight="280px" />
                </ResultCard>
              )}

              {result.operationalized_knowledge && (
                <ResultCard
                  title="Operationalized knowledge bundle"
                  description="Structured records, retrieval documents, and graph-ready entities derived from the extracted guideline evidence."
                  copyContent={JSON.stringify(result.operationalized_knowledge, null, 2)}
                >
                  <ResultJson data={result.operationalized_knowledge} maxHeight="320px" />
                </ResultCard>
              )}

              {result.validation && (
                <ResultCard
                  title="Validation output"
                  description="Validator response grounded against the rendered source pages that were supplied for review."
                  copyContent={JSON.stringify(result.validation, null, 2)}
                >
                  <ResultJson data={result.validation} maxHeight="280px" />
                </ResultCard>
              )}

              <ResultCard
                title="Parsed source preview"
                description="The text/markdown passed into the clinical extractor."
                copyContent={result.parsed_documents.join("\n\n---\n\n")}
              >
                <ResultText
                  content={result.parsed_documents.join("\n\n---\n\n")}
                  maxHeight="320px"
                />
              </ResultCard>

              {result.route && (
                <ResultCard
                  title="Adaptive parser route"
                  description="The parser selection plan and any fallbacks that were available for this source file."
                  copyContent={JSON.stringify(result.route, null, 2)}
                >
                  <ResultJson data={result.route} maxHeight="240px" />
                </ResultCard>
              )}
            </>
          ) : (
            <EmptyStateCard
              title="No extraction run yet"
              description="Upload a clinical guideline or load an uploaded example to generate traceable structured knowledge."
              icon={HeartPulse}
            />
          )}
        </div>
      </div>
    </div>
  );
}

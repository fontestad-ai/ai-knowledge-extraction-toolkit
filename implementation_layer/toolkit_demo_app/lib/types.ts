/**
 * Shared types used across the standalone clinical application
 */

/**
 * Workflow types available in the application
 */
export type DemoType = "clinical-extraction";

/**
 * Represents a source citation from document retrieval
 */
export interface Source {
  documentName: string;
  pageNumber: string | number | null;
  relevanceScore?: number | null;
}

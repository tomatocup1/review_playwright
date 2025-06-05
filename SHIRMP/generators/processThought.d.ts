export interface ProcessThoughtPromptParams {
    thought: string;
    thoughtNumber: number;
    totalThoughts: number;
    nextThoughtNeeded: boolean;
    stage: string;
    tags: string[];
    axioms_used: string[];
    assumptions_challenged: string[];
}
export declare function getProcessThoughtPrompt(param: ProcessThoughtPromptParams): string;

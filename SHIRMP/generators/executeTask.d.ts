/**
 * executeTask prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
import { Task } from "../../types/index.js";
/**
 * 任務複雜度評估的介面
 */
interface ComplexityAssessment {
    level: string;
    metrics: {
        descriptionLength: number;
        dependenciesCount: number;
    };
    recommendations?: string[];
}
/**
 * executeTask prompt 參數介面
 */
export interface ExecuteTaskPromptParams {
    task: Task;
    complexityAssessment?: ComplexityAssessment;
    relatedFilesSummary?: string;
    dependencyTasks?: Task[];
}
/**
 * 獲取 executeTask 的完整 prompt
 * @param params prompt 參數
 * @returns 生成的 prompt
 */
export declare function getExecuteTaskPrompt(params: ExecuteTaskPromptParams): string;
export {};

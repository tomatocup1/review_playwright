/**
 * planTask prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
import { Task } from "../../types/index.js";
/**
 * planTask prompt 參數介面
 */
export interface PlanTaskPromptParams {
    description: string;
    requirements?: string;
    existingTasksReference?: boolean;
    completedTasks?: Task[];
    pendingTasks?: Task[];
    memoryDir: string;
}
/**
 * 獲取 planTask 的完整 prompt
 * @param params prompt 參數
 * @returns 生成的 prompt
 */
export declare function getPlanTaskPrompt(params: PlanTaskPromptParams): string;

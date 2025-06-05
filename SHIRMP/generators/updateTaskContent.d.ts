/**
 * updateTaskContent prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
import { Task } from "../../types/index.js";
/**
 * updateTaskContent prompt 參數介面
 */
export interface UpdateTaskContentPromptParams {
    taskId: string;
    task?: Task;
    success?: boolean;
    message?: string;
    validationError?: string;
    emptyUpdate?: boolean;
    updatedTask?: Task;
}
/**
 * 獲取 updateTaskContent 的完整 prompt
 * @param params prompt 參數
 * @returns 生成的 prompt
 */
export declare function getUpdateTaskContentPrompt(params: UpdateTaskContentPromptParams): string;

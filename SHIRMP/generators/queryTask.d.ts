/**
 * queryTask prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
import { Task } from "../../types/index.js";
/**
 * queryTask prompt 參數介面
 */
export interface QueryTaskPromptParams {
    query: string;
    isId: boolean;
    tasks: Task[];
    totalTasks: number;
    page: number;
    pageSize: number;
    totalPages: number;
}
/**
 * 獲取 queryTask 的完整 prompt
 * @param params prompt 參數
 * @returns 生成的 prompt
 */
export declare function getQueryTaskPrompt(params: QueryTaskPromptParams): string;

/**
 * prompt 載入器
 * 提供從環境變數載入自定義 prompt 的功能
 */
/**
 * 載入 prompt，支援環境變數自定義
 * @param basePrompt 基本 prompt 內容
 * @param promptKey prompt 的鍵名，用於生成環境變數名稱
 * @returns 最終的 prompt 內容
 */
export declare function loadPrompt(basePrompt: string, promptKey: string): string;
/**
 * 生成包含動態參數的 prompt
 * @param promptTemplate prompt 模板
 * @param params 動態參數
 * @returns 填充參數後的 prompt
 */
export declare function generatePrompt(promptTemplate: string, params?: Record<string, any>): string;
/**
 * 從模板載入 prompt
 * @param templatePath 相對於模板集根目錄的模板路徑 (e.g., 'chat/basic.md')
 * @returns 模板內容
 * @throws Error 如果找不到模板文件
 */
export declare function loadPromptFromTemplate(templatePath: string): string;

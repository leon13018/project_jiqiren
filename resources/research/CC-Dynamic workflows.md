> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# 使用動態工作流程大規模協調子代理

> 動態工作流程從 Claude 編寫的指令碼協調許多子代理，您可以重新執行。用於程式碼庫審計、大規模遷移和交叉檢查研究。

{/* plan-availability: feature=workflows plans=pro,max,team,enterprise providers=all */}

<Note>
  Dynamic workflows 處於研究預覽階段。它們需要 Claude Code v2.1.154 或更新版本，並在所有付費方案上可用，具有 Anthropic API 存取權限，以及在 Amazon Bedrock、Google Cloud Vertex AI 和 Microsoft Foundry 上可用。在 Pro 上，從 `/config` 中的 Dynamic workflows 列啟用它們。
</Note>

動態工作流程是一個 JavaScript 指令碼，可大規模協調[子代理](/zh-TW/sub-agents)。Claude 為您描述的任務編寫指令碼，執行時期在背景執行它，同時您的工作階段保持回應。

當任務需要超過一個對話可以協調的代理數量時，或當您想將協調編成可以讀取和重新執行的指令碼時，請使用工作流程。範例包括程式碼庫範圍的錯誤掃描、500 個檔案遷移、需要相互交叉檢查來源的研究問題，以及值得從多個獨立角度起草的困難計畫，然後再提交給其中一個。

本頁涵蓋如何：

* 決定[何時使用工作流程](#when-to-use-a-workflow)而不是子代理或技能
* [執行捆綁的工作流程](#run-a-bundled-workflow)與 `/deep-research`
* [讓 Claude 為您的任務編寫工作流程](#have-claude-write-a-workflow)並儲存它
* 瞭解[工作流程如何執行](#how-a-workflow-runs)和[管理執行](#manage-runs)

## 何時使用工作流程

[子代理](/zh-TW/sub-agents)、[技能](/zh-TW/skills)和工作流程都可以執行多步驟任務。區別在於誰掌握計畫：

|            | 子代理           | 技能            | 工作流程         |
| :--------- | :------------ | :------------ | :----------- |
| 它是什麼       | Claude 生成的工作者 | Claude 遵循的指示  | 執行時期執行的指令碼   |
| 誰決定接下來執行什麼 | Claude，逐輪     | Claude，遵循提示   | 指令碼          |
| 中間結果在哪裡    | Claude 的上下文視窗 | Claude 的上下文視窗 | 指令碼變數        |
| 什麼是可重複的    | 工作者定義         | 指示            | 協調本身         |
| 規模         | 每輪委派的幾項任務     | 與子代理相同        | 每次執行數十到數百個代理 |
| 中斷         | 重新啟動輪次        | 重新啟動輪次        | 在同一工作階段中可恢復  |

工作流程將計畫移入程式碼。使用子代理和技能，Claude 是協調者：它逐輪決定接下來要生成什麼，每個結果都進入 Claude 的上下文。工作流程指令碼保存迴圈、分支和中間結果本身，因此 Claude 的上下文只保存最終答案。

將計畫移入程式碼也讓工作流程應用可重複的品質模式，而不僅僅是執行更多代理：它可以讓獨立代理在報告前對彼此的發現進行對抗性審查，或從多個角度起草計畫並相互權衡，因此您獲得比單次通過更可信的結果。

## 執行捆綁的工作流程

查看工作流程運作的最快方式是執行 `/deep-research`，[內建工作流程](#bundled-workflows)Claude Code 包含用於跨許多來源調查問題。您將看到代理在背景中完成一組階段，同時您的工作階段保持自由，最後獲得一份報告而不是逐輪記錄。

<Steps>
  <Step title="執行工作流程">
    使用您想調查的問題執行 `/deep-research`。它在多個角度上展開網路搜尋，獲取並交叉檢查它找到的來源，並合成引用的報告。

    ```text theme={null}
    /deep-research What changed in the Node.js permission model between v20 and v22?
    ```
  </Step>

  <Step title="允許工作流程">
    Claude Code 詢問是否允許工作流程。選擇**是**以繼續。確切的提示取決於您的權限模式。有關每種模式選項，請參閱[在執行前批准計畫](#approve-the-plan-before-it-runs)。
  </Step>

  <Step title="監視進度">
    執行在背景中啟動。執行 `/workflows`，使用箭頭鍵選擇執行，然後按 Enter 開啟其進度檢視：

    ```text theme={null}
    /workflows
    ```

    檢視顯示每個階段及其代理計數、令牌總計和經過時間。深入任何階段以查看其代理及每個代理發現的內容。有關完整的控制集，請參閱[監視執行](#watch-the-run)。

    您也可以從輸入框下方的任務面板監視：執行進行時會出現一行進度摘要。按向下箭頭聚焦它，然後按 Enter 展開。
  </Step>

  <Step title="閱讀報告">
    執行完成後，報告進入您的工作階段。它引用每項聲明來自的來源，未通過交叉檢查的聲明已被篩選出去。
  </Step>
</Steps>

要為您自己的任務執行工作流程，[讓 Claude 編寫一個](#have-claude-write-a-workflow)，一旦執行執行您想要的操作，您可以[儲存它](#save-the-workflow-for-reuse)作為您自己的命令。

### 捆綁的工作流程

Claude Code 包含 `/deep-research` 作為內建工作流程：

| 命令                          | 它做什麼                                                                                                                                  |
| :-------------------------- | :------------------------------------------------------------------------------------------------------------------------------------ |
| `/deep-research <question>` | 在多個角度上展開網路搜尋問題，獲取並交叉檢查它找到的來源，對每項聲明進行投票，並返回引用的報告，其中未通過交叉檢查的聲明已被篩選出去。需要[WebSearch 工具](/zh-TW/tools-reference#websearch-tool-behavior)可用 |

[您自己儲存的工作流程](#save-the-workflow-for-reuse)以相同方式成為命令，並在 `/` 自動完成中與捆綁的命令一起出現。

### 監視執行

工作流程在背景中執行，因此工作階段在代理工作時保持回應。隨時執行 `/workflows` 以列出執行中和已完成的工作流程，然後選擇一個以開啟其進度檢視。

```text theme={null}
/workflows
```

進度檢視顯示每個階段及其代理計數、令牌總計和經過時間。頁腳列出每個動作的鍵：

| 鍵             | 動作                                           |
| :------------ | :------------------------------------------- |
| `↑` / `↓`     | 選擇階段或代理                                      |
| `Enter` 或 `→` | 深入選定的階段，然後進入代理以讀取其提示、最近的工具呼叫和結果              |
| `Esc`         | 返回一個級別                                       |
| `j` / `k`     | 當代理詳細資訊溢出時在其中捲動                              |
| `p`           | 暫停或恢復執行                                      |
| `x`           | 停止選定的代理，或當焦點在執行上時停止整個工作流程                    |
| `r`           | 重新啟動選定的執行中代理                                 |
| `s`           | [儲存](#save-the-workflow-for-reuse)執行的指令碼作為命令 |

## 讓 Claude 編寫工作流程

您可以通過兩種方式讓 Claude 為您的任務編寫工作流程：

* [在您的提示中要求工作流程](#ask-for-a-workflow-in-your-prompt)，使用單詞 `workflow`，Claude 為任務編寫一個。
* [讓 Claude 使用 ultracode 決定](#let-claude-decide-with-ultracode)：設定 `/effort ultracode`，Claude 為工作階段中的每項實質性任務規劃工作流程。

您也可以執行已存在的工作流程命令：[捆綁的工作流程](#bundled-workflows)如 `/deep-research`，或您[儲存的](#save-the-workflow-for-reuse)工作流程。

### 在您的提示中要求工作流程

要在不改變工作階段努力級別的情況下將單個任務作為工作流程執行，請在提示中的任何位置包含單詞 `workflow`。

```text theme={null}
Run a workflow to audit every API endpoint under src/routes/ for missing auth checks
```

Claude Code 在您的輸入中突出顯示該單詞，Claude 為任務編寫工作流程指令碼，而不是逐輪完成它。

如果執行執行您想要的操作，您可以之後[將其儲存為命令](#save-the-workflow-for-reuse)。

如果 Claude Code 在您不打算觸發工作流程時突出顯示該單詞，請按 `alt+w` 為此提示忽略它，或在游標位於突出顯示單詞的正後方時按退格鍵。要停止該單詞完全觸發，請在 `/config` 中關閉 Workflow keyword trigger。

### 讓 Claude 使用 ultracode 決定

Ultracode 是一個 Claude Code 設定，結合 `xhigh` [推理努力](/zh-TW/model-config#adjust-effort-level)與自動工作流程協調。啟用它後，Claude 為每項實質性任務規劃工作流程，而不是等待您要求。

```text theme={null}
/effort ultracode
```

啟用 ultracode 後，Claude 決定任務何時值得工作流程。單個請求可以變成一系列工作流程：一個用於理解程式碼，一個用於進行更改，一個用於驗證它。這適用於工作階段中的每項任務，因此每個請求使用更多令牌並花費比較低努力級別更長的時間。

Ultracode 持續當前工作階段，當您啟動新工作階段時重設。當您返回日常工作時，使用 `/effort high` 下降。它在支援 `xhigh` [努力](/zh-TW/model-config#adjust-effort-level)的模型上可用；在其他模型上，`/effort` 功能表不提供它。

### 在執行前批准計畫

在 CLI 中，每次執行提示顯示計畫的階段和這些選項：

* **是，執行它**：啟動執行
* **是，不再詢問 `<name>` 在 `<path>` 中**：啟動，並從現在開始跳過此專案中此工作流程的此提示
* **檢視原始指令碼**：在決定前讀取指令碼
* **否**：取消

`Ctrl+G` 在您的編輯器中開啟指令碼。`Tab` 讓您在執行啟動前調整提示。

您是否看到此提示取決於您的[權限模式](/zh-TW/permission-modes)：

| 權限模式                       | 何時提示您                                                      |
| :------------------------- | :--------------------------------------------------------- |
| 預設、接受編輯                    | 每次執行，除非您已為此專案中的該工作流程選擇**是，不再詢問**                           |
| 自動                         | 首次啟動。任何**是**在您的使用者設定中記錄同意，稍後啟動無需提示即可啟動。當 ultracode 啟用時完全跳過 |
| 繞過權限、`claude -p`、Agent SDK | 從不。執行立即啟動                                                  |

在桌面應用程式中，批准卡顯示工作流程名稱、階段列表和令牌使用警告，具有**一次**、**始終**和**拒絕**動作。進度檢視出現在背景任務側窗格中。

您的權限模式僅控制上面的啟動提示。工作流程生成的子代理始終在 `acceptEdits` 模式下執行，並繼承您的[工具允許清單](/zh-TW/settings#permission-settings)，無論您的工作階段模式如何。檔案編輯自動批准。

Shell 命令、網路獲取和不在您允許清單中的 MCP 工具仍可在執行中提示您。要在長時間執行時避免這種情況，請在啟動前將代理需要的命令新增到您的允許清單。

在 `claude -p` 和 Agent SDK 中沒有人提示，因此工具呼叫遵循您配置的權限規則，無需互動確認。

### 儲存工作流程以供重複使用

當 Claude 為您將重複的任務編寫工作流程時，您可以將該執行的指令碼儲存為命令。您在每個分支上執行的審查流程然後每次執行相同的協調。

執行 `/workflows`，選擇您想保留的執行，然後按 `s`。在儲存對話中，Tab 在兩個儲存位置之間切換：

* `.claude/workflows/` 在您的專案中：與克隆儲存庫的每個人共享
* `~/.claude/workflows/` 在您的主目錄中：在每個專案中可用，僅對您可見

按 Enter 儲存。工作流程在未來工作階段中從任一位置作為 `/<name>` 執行。

如果專案工作流程和個人工作流程共享名稱，則執行專案工作流程。

## 工作流程如何執行

工作流程執行時期在隔離環境中執行指令碼，與您的對話分開。中間結果保留在指令碼變數中，而不是進入 Claude 的上下文。

執行時期在執行進行時追蹤每個代理的結果，這是使執行在同一工作階段中[可恢復](#resume-after-a-pause)的原因。

### 行為和限制

執行時期應用以下約束：

| 約束                           | 為什麼                                        |
| :--------------------------- | :----------------------------------------- |
| 無中途使用者輸入                     | 只有代理權限提示可以暫停執行。對於階段之間的簽核，將每個階段作為其自己的工作流程執行 |
| 無來自工作流程本身的直接檔案系統或 shell 存取   | 代理讀取、寫入和執行命令。指令碼協調代理                       |
| 最多 16 個並行代理，在 CPU 核心有限的機器上更少 | 限制本地資源使用                                   |
| 每次執行 1,000 個代理               | 防止失控迴圈                                     |

## 管理執行

執行啟動後，您從 `/workflows` 檢視或通過展開輸入框下方任務面板中的進度線來管理它。

### 暫停後恢復

如果您停止執行，您可以恢復它：已完成的代理返回其快取結果，其餘的實時執行。從 `/workflows` 恢復暫停的執行，方法是選擇它並按 `p`，或要求 Claude 使用相同指令碼重新啟動工作流程。

恢復在同一 Claude Code 工作階段內工作。如果您在工作流程執行時退出 Claude Code，下一個工作階段將重新啟動工作流程。

### 成本

工作流程生成許多代理，因此單次執行可以使用比在對話中完成相同任務更多的令牌。執行計入您的方案使用量和速率限制，如任何其他工作階段。您可以隨時從 `/workflows` 停止執行中的工作流程，而不會丟失已完成的工作。

工作流程中的每個代理使用您的工作階段模型，除非指令碼將階段路由到不同的模型。要控制模型成本：

* 在大型執行前檢查 `/model`，如果您通常為日常工作切換到較小的模型
* 當您描述任務時，要求 Claude 為不需要最強模型的階段使用較小的模型

### 關閉工作流程

工作流程在 CLI、桌面應用程式、IDE 擴充功能、[非互動模式](/zh-TW/headless)與 `claude -p` 和 [Agent SDK](/zh-TW/agent-sdk/overview) 中可用。相同的禁用設定適用於每個表面。

要為自己關閉工作流程：

* 在 `/config` 中切換 Dynamic workflows 關閉。在工作階段中持續。
* 在 `~/.claude/settings.json` 中設定 `"disableWorkflows": true`。在工作階段中持續。
* 設定 `CLAUDE_CODE_DISABLE_WORKFLOWS=1`。在啟動時讀取，因此它適用於您設定它的任何位置。

要為整個組織關閉工作流程，在[受管設定](/zh-TW/server-managed-settings)中設定 `"disableWorkflows": true`，或使用 [Claude Code 管理員設定](https://claude.ai/admin-settings/claude-code)頁面上的切換。

禁用工作流程時，捆綁的工作流程命令不可用，`workflow` 關鍵字不再觸發執行，`ultracode` 從 `/effort` 功能表中移除。

## 相關資源

* [並行執行代理](/zh-TW/agents)：比較子代理、代理檢視、代理團隊和工作流程
* [建立自訂子代理](/zh-TW/sub-agents)：工作流程協調的工作者原始類型
* [管理成本](/zh-TW/costs)：多代理執行如何計入使用限制

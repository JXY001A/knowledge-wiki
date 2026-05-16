# DeepSeek API 定价

来源：https://api-docs.deepseek.com/zh-cn/quick_start/pricing

## 模型 & 价格

下表所列模型价格以"百万 tokens"为单位。Token 是模型用来表示自然语言文本的的最小单位，可以是一个词、一个数字或一个标点符号等。我们将根据模型输入和输出的总 token 数进行计量计费。

## 模型细节

| | | deepseek-v4-flash (1) | deepseek-v4-pro |
|---|---|---|---|
| **模型** | | DeepSeek-V4-Flash | DeepSeek-V4-Pro |
| **BASE URL (OpenAI 格式)** | | https://api.deepseek.com/ | https://api.deepseek.com/ |
| **BASE URL (Anthropic 格式)** | | https://api.deepseek.com/anthropic | https://api.deepseek.com/anthropic |
| **思考模式** | | 支持非思考与思考模式（默认） | 支持非思考与思考模式（默认） |
| **上下文长度** | | 1M | 1M |
| **输出长度** | | 最大 384K | 最大 384K |
| **功能** | Json Output | 支持 | 支持 |
| | Tool Calls | 支持 | 支持 |
| | 对话前缀续写（Beta）| 支持 | 支持 |
| | FIM 补全（Beta） | 仅非思考模式支持 | 仅非思考模式支持 |
| **价格** | 百万tokens输入（缓存命中）(2) | 0.02元 | 0.025元（2.5折 (3)） ~~0.1元~~ |
| | 百万tokens输入（缓存未命中） | 1元 | 3元（2.5折 (3)） ~~12元~~ |
| | 百万tokens输出 | 2元 | 6元（2.5折 (3)） ~~24元~~ |

(1) deepseek-chat 与 deepseek-reasoner 两个模型名将于日后弃用。出于兼容考虑，二者分别对应 deepseek-v4-flash 的非思考与思考模式。  
(2) 全系列模型，输入缓存命中的价格已降至首发价格的 1/10，该价格调整自北京时间 2026/4/26 20:15 起生效  
(3) **当前 deepseek-v4-pro 模型 2.5 折，优惠期延长至北京时间 2026/05/31 23:59。**

## 扣费规则

扣减费用 = token 消耗量 × 模型单价，对应的费用将直接从充值余额或赠送余额中进行扣减。 当充值余额与赠送余额同时存在时，优先扣减赠送余额。

产品价格可能发生变动，DeepSeek 保留修改价格的权利。请您依据实际用量按需充值，定期查看此页面以获知最新价格信息。

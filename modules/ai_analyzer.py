"""
AI Content Analyzer using Google Gemini API (Free Tier).
Analyzes podcast transcripts to extract stock mentions, industry trends,
and generates structured investment advice.
"""

import json
import logging
import time
import re

logger = logging.getLogger(__name__)

# Retry configuration for API rate limits
MAX_RETRIES = 3
BASE_DELAY = 10  # seconds


def _get_client(api_key):
    """Initialize Gemini client."""
    from google import genai
    return genai.Client(api_key=api_key)


FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


def _call_gemini(client, prompt, retries=MAX_RETRIES):
    """Call Gemini API with model fallback and exponential backoff."""
    last_error = None

    for model_name in FALLBACK_MODELS:
        for attempt in range(retries):
            try:
                logger.info("Calling Gemini model: %s (attempt %d)", model_name, attempt + 1)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response.text
            except Exception as e:
                last_error = e
                error_str = str(e)
                if '429' in error_str or 'quota' in error_str.lower():
                    delay = BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Rate limited on %s (attempt %d/%d). Waiting %ds...",
                        model_name, attempt + 1, retries, delay
                    )
                    time.sleep(delay)
                elif '503' in error_str or 'UNAVAILABLE' in error_str:
                    logger.warning("Model %s unavailable, trying next model...", model_name)
                    break  # Skip to next model
                else:
                    logger.error("Gemini API error on %s: %s", model_name, e)
                    if attempt < retries - 1:
                        time.sleep(5)
                    else:
                        break  # Try next model

    raise Exception(f"All Gemini models failed. Last error: {last_error}")


def _extract_json(text):
    """Extract JSON from Gemini response text (may contain markdown code blocks)."""
    # Try to find JSON in code blocks
    json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    # Try to parse directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object or array
    for pattern in [r'\{.*\}', r'\[.*\]']:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue

    logger.error("Failed to extract JSON from response:\n%s", text[:500])
    return None


def analyze_content(transcript, api_key):
    """
    Analyze podcast transcript to extract stock mentions and investment insights.
    
    Args:
        transcript: Full text transcript of the podcast
        api_key: Google Gemini API key
    
    Returns:
        dict with keys: stocks, sectors, macro_views, summary
    """
    client = _get_client(api_key)

    # Truncate very long transcripts to avoid token limits
    max_chars = 50000
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars]
        logger.warning("Transcript truncated to %d chars", max_chars)

    prompt = f"""你是一位專業的台灣股市分析師，專門分析財經Podcast「股癌」的內容。
請仔細分析以下節目逐字稿，提取所有與股票投資相關的資訊。

## 分析要求

1. **提及的個股**：找出所有被討論到的股票，包括：
   - 股票代號（台股用數字如 2330，美股用英文如 AAPL）
   - 股票名稱
   - 市場（TW=台股, US=美股）
   - 情緒判斷（bullish=看多, bearish=看空, neutral=中性）
   - 主委對該股的觀點摘要（用繁體中文）
   - 所屬產業/類股

2. **產業趨勢**：分析提到的產業趨勢和看法

3. **總體經濟觀點**：利率、匯率、通膨、Fed政策等看法

4. **節目摘要**：用3-5個重點總結本集內容

## 重要規則
- 只提取「明確被討論」的股票，不要猜測
- 如果主委對某檔股票只是順帶提到但沒有明確觀點，sentiment 設為 neutral
- 台股代號必須是正確的數字代號（如台積電=2330, 聯發科=2454, 鴻海=2317）
- 如果無法確認股票代號，stock_symbol 填寫股票名稱
- 所有文字內容使用繁體中文

## 輸出格式（嚴格JSON）

```json
{{
  "stocks": [
    {{
      "stock_symbol": "2330",
      "stock_name": "台積電",
      "market": "TW",
      "sentiment": "bullish",
      "gooaye_opinion": "主委認為...",
      "sector": "半導體"
    }}
  ],
  "sectors": [
    {{
      "name": "半導體",
      "outlook": "正面/負面/中性",
      "analysis": "分析內容..."
    }}
  ],
  "macro_views": [
    {{
      "topic": "Fed利率政策",
      "view": "觀點內容..."
    }}
  ],
  "summary": [
    "重點一...",
    "重點二...",
    "重點三..."
  ]
}}
```

## 節目逐字稿

{transcript}
"""

    logger.info("Analyzing transcript with Gemini (%d chars)...", len(transcript))
    response_text = _call_gemini(client, prompt)

    result = _extract_json(response_text)
    if result is None:
        logger.error("Failed to parse AI analysis response")
        return {
            'stocks': [],
            'sectors': [],
            'macro_views': [],
            'summary': ['分析失敗：無法解析 AI 回應']
        }

    # Validate structure
    if 'stocks' not in result:
        result['stocks'] = []
    if 'sectors' not in result:
        result['sectors'] = []
    if 'macro_views' not in result:
        result['macro_views'] = []
    if 'summary' not in result:
        result['summary'] = []

    logger.info("Analysis complete: found %d stocks, %d sectors",
                len(result['stocks']), len(result['sectors']))

    return result


def generate_investment_advice(stock_info, stock_data, api_key):
    """
    Generate detailed investment advice for a stock based on Gooaye's opinion
    and current market data.
    
    Args:
        stock_info: Dict with stock_symbol, stock_name, sentiment, gooaye_opinion, sector
        stock_data: Dict with current_price, history, fundamentals etc.
        api_key: Gemini API key
    
    Returns:
        dict with target_price, buy_price, stop_loss, short/mid/long_term_advice, analysis_detail
    """
    client = _get_client(api_key)

    # Format stock data for the prompt
    data_str = json.dumps(stock_data, ensure_ascii=False, indent=2, default=str)
    info_str = json.dumps(stock_info, ensure_ascii=False, indent=2)

    prompt = f"""你是一位資深的台灣股市投資分析師。請根據以下資訊，為這檔股票提供完整的投資建議。

## 股癌主委的觀點
{info_str}

## 股票市場數據
{data_str}

## 請提供以下分析（以繁體中文回答）

請根據股癌主委的觀點結合實際市場數據，提供專業但易懂的投資建議。

## 輸出格式（嚴格JSON）

```json
{{
  "target_price": 目標價（數字，根據技術面和基本面估算），
  "buy_price": 建議買入價（數字，合理的進場價位），
  "stop_loss": 停損價（數字，風險控制價位），
  "short_term_advice": "短期（1-3個月）投資建議，包含理由和策略",
  "mid_term_advice": "中期（3-12個月）投資建議，包含理由和策略",
  "long_term_advice": "長期（1年以上）投資建議，包含理由和策略",
  "analysis_detail": "完整的分析報告，包含：\\n1. 基本面分析\\n2. 技術面分析\\n3. 產業面分析\\n4. 風險因素\\n5. 投資評級（強烈推薦/推薦/持有/減碼/避開）"
}}
```

注意：
- 價格必須是合理的數字，基於目前股價和技術分析
- 如果是台股，價格單位為新台幣
- 如果是美股，價格單位為美元
- 分析應客觀專業，同時參考股癌主委的觀點
- 必須包含風險提示
"""

    logger.info("Generating investment advice for %s (%s)...",
                stock_info.get('stock_name'), stock_info.get('stock_symbol'))

    response_text = _call_gemini(client, prompt)
    result = _extract_json(response_text)

    if result is None:
        logger.error("Failed to parse investment advice response")
        return {
            'target_price': None,
            'buy_price': None,
            'stop_loss': None,
            'short_term_advice': '分析暫時無法生成',
            'mid_term_advice': '分析暫時無法生成',
            'long_term_advice': '分析暫時無法生成',
            'analysis_detail': '分析暫時無法生成',
        }

    # Ensure all keys exist
    for key in ['target_price', 'buy_price', 'stop_loss',
                'short_term_advice', 'mid_term_advice', 'long_term_advice',
                'analysis_detail']:
        if key not in result:
            result[key] = None

    # Convert price fields to float
    for key in ['target_price', 'buy_price', 'stop_loss']:
        if result[key] is not None:
            try:
                result[key] = float(result[key])
            except (ValueError, TypeError):
                result[key] = None

    return result

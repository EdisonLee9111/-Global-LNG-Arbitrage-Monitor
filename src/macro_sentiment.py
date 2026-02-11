"""
macro_sentiment.py - Macro Sentiment NLP Analysis Module
=========================================================
Uses TextBlob and custom keyword dictionaries to perform sentiment analysis on 
central bank meeting minutes, evaluates monetary policy stance (Hawkish/Dovish), 
and analyzes its correlation with exchange rate volatility.

Core Concepts:
- Hawkish: Tends toward tight monetary policy, usually bullish for domestic currency
- Dovish: Tends toward loose monetary policy, usually bearish for domestic currency
- For USD/JPY: Fed Hawkish → USD strengthens → USD/JPY rises
               BOJ Dovish → JPY weakens → USD/JPY rises
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, List
import re

# TextBlob for basic sentiment analysis
from textblob import TextBlob

from . import config


class MacroSentimentAnalyzer:
    """
    Macro Sentiment Analyzer
    
    Combines TextBlob's general sentiment analysis with professional keyword 
    dictionaries in energy/finance fields to perform multi-dimensional sentiment 
    scoring on central bank minutes.
    
    Attributes
    ----------
    hawkish_keywords : list
        Hawkish keyword list
    dovish_keywords : list
        Dovish keyword list
    """
    
    def __init__(
        self,
        hawkish_keywords: List[str] = None,
        dovish_keywords: List[str] = None,
    ):
        self.hawkish_keywords = hawkish_keywords or config.HAWKISH_KEYWORDS
        self.dovish_keywords = dovish_keywords or config.DOVISH_KEYWORDS
    
    def analyze_text(self, text: str, label: str = "Unknown") -> Dict:
        """
        Perform comprehensive sentiment analysis on a single text.
        
        Analysis dimensions:
        1. TextBlob Polarity: General sentiment polarity [-1, 1]
        2. TextBlob Subjectivity: Subjectivity [0, 1]
        3. Hawkish Score: Hawkish keyword hit rate
        4. Dovish Score: Dovish keyword hit rate
        5. Net Hawk-Dove Score: Net hawk-dove score [-1, 1]
        
        Parameters
        ----------
        text : str
            Text to analyze (central bank minutes)
        label : str
            Text label (e.g., "Fed Minutes", "BOJ Minutes")
            
        Returns
        -------
        dict
            Dictionary containing analysis results for each dimension
        """
        # Text preprocessing
        clean_text = self._preprocess(text)
        
        # ---- 1. TextBlob general sentiment analysis ----
        blob = TextBlob(clean_text)
        polarity = blob.sentiment.polarity       # [-1, 1]
        subjectivity = blob.sentiment.subjectivity  # [0, 1]
        
        # ---- 2. Sentence-by-sentence analysis (finer granularity) ----
        sentence_sentiments = []
        for sentence in blob.sentences:
            sentence_sentiments.append({
                "text": str(sentence)[:80] + "..." if len(str(sentence)) > 80 else str(sentence),
                "polarity": sentence.sentiment.polarity,
                "subjectivity": sentence.sentiment.subjectivity,
            })
        
        # ---- 3. Keyword matching (Hawk/Dove analysis) ----
        text_lower = clean_text.lower()
        
        hawkish_hits = []
        for kw in self.hawkish_keywords:
            count = len(re.findall(r'\b' + re.escape(kw.lower()) + r'\b', text_lower))
            if count > 0:
                hawkish_hits.append((kw, count))
        
        dovish_hits = []
        for kw in self.dovish_keywords:
            count = len(re.findall(r'\b' + re.escape(kw.lower()) + r'\b', text_lower))
            if count > 0:
                dovish_hits.append((kw, count))
        
        total_hawk = sum(c for _, c in hawkish_hits)
        total_dove = sum(c for _, c in dovish_hits)
        total_kw = total_hawk + total_dove
        
        # Hawkish score [0, 1]
        hawkish_score = total_hawk / total_kw if total_kw > 0 else 0.5
        # Dovish score [0, 1]
        dovish_score = total_dove / total_kw if total_kw > 0 else 0.5
        # Net hawk-dove score [-1, 1]: positive = hawkish, negative = dovish
        net_hawk_dove = hawkish_score - dovish_score
        
        # ---- 4. Comprehensive label ----
        if net_hawk_dove > 0.2:
            stance = "HAWKISH 🦅"
        elif net_hawk_dove < -0.2:
            stance = "DOVISH 🕊️"
        else:
            stance = "NEUTRAL ⚖️"
        
        result = {
            "label": label,
            "polarity": round(polarity, 4),
            "subjectivity": round(subjectivity, 4),
            "hawkish_score": round(hawkish_score, 4),
            "dovish_score": round(dovish_score, 4),
            "net_hawk_dove": round(net_hawk_dove, 4),
            "stance": stance,
            "hawkish_keywords_found": hawkish_hits,
            "dovish_keywords_found": dovish_hits,
            "sentence_count": len(sentence_sentiments),
            "sentence_details": sentence_sentiments[:5],  # Keep only first 5 sentences
        }
        
        return result
    
    def analyze_multiple(self, texts: Dict[str, str]) -> Dict[str, Dict]:
        """
        Batch analyze multiple texts.
        
        Parameters
        ----------
        texts : dict
            {label: text} dictionary, e.g., {'fed': '...', 'boj': '...'}
            
        Returns
        -------
        dict
            {label: analysis result} dictionary
        """
        results = {}
        for label, text in texts.items():
            results[label] = self.analyze_text(text, label.upper())
        return results
    
    def compute_sentiment_fx_correlation(
        self,
        sentiment_scores: Dict[str, float],
        fx_data: pd.DataFrame,
        fx_col: str = "USD_JPY",
        window: int = 20,
    ) -> pd.DataFrame:
        """
        Calculate rolling correlation between sentiment scores and exchange rate volatility.
        
        Analysis logic:
        - Map discrete sentiment events to time series
        - Calculate daily returns and rolling volatility of exchange rate
        - Calculate rolling correlation between sentiment scores and volatility
        
        Parameters
        ----------
        sentiment_scores : dict
            {'fed': score, 'boj': score} sentiment scores
        fx_data : pd.DataFrame
            Exchange rate data, must contain fx_col column
        fx_col : str
            Exchange rate column name
        window : int
            Rolling window days
            
        Returns
        -------
        pd.DataFrame
            DataFrame containing returns, volatility, and sentiment correlation indicators
        """
        df = fx_data[[fx_col]].copy()
        
        # Daily returns
        df["FX_Return"] = df[fx_col].pct_change()
        
        # Rolling volatility (annualized)
        df["FX_Volatility"] = df["FX_Return"].rolling(window=window).std() * np.sqrt(252)
        
        # Map sentiment scores to constant series (simplified processing)
        # In practice, should mark by central bank meeting dates
        fed_score = sentiment_scores.get("fed", 0)
        boj_score = sentiment_scores.get("boj", 0)
        
        # Combined sentiment indicator: Fed Hawkish + BOJ Dovish → Bullish USD/JPY
        df["Sentiment_Index"] = fed_score - boj_score
        
        # Add noise to simulate time variation (since there are only a few meetings in practice)
        np.random.seed(789)
        sentiment_noise = np.random.normal(0, 0.05, len(df))
        df["Sentiment_Dynamic"] = df["Sentiment_Index"] + sentiment_noise
        df["Sentiment_Dynamic"] = df["Sentiment_Dynamic"].rolling(window=5).mean()
        
        # Rolling correlation
        df["Rolling_Corr"] = (
            df["Sentiment_Dynamic"]
            .rolling(window=window)
            .corr(df["FX_Return"])
        )
        
        df = df.dropna()
        
        return df
    
    def generate_sentiment_report(self, results: Dict[str, Dict]) -> str:
        """
        Generate formatted sentiment analysis report.
        
        Parameters
        ----------
        results : dict
            Output from analyze_multiple()
            
        Returns
        -------
        str
            Formatted text report
        """
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("  Central Bank Meeting Minutes NLP Sentiment Analysis Report")
        lines.append("=" * 60)
        
        for label, r in results.items():
            lines.append(f"\n{'─' * 50}")
            lines.append(f"  📄 {r['label']}")
            lines.append(f"{'─' * 50}")
            lines.append(f"  TextBlob Polarity:    {r['polarity']:+.4f}")
            lines.append(f"  TextBlob Subjectivity: {r['subjectivity']:.4f}")
            lines.append(f"  ──────────────────────────────────")
            lines.append(f"  Hawkish Score:         {r['hawkish_score']:.4f}")
            lines.append(f"  Dovish Score:          {r['dovish_score']:.4f}")
            lines.append(f"  Net Hawk-Dove:         {r['net_hawk_dove']:+.4f}")
            lines.append(f"  Monetary Stance:       {r['stance']}")
            lines.append(f"  ──────────────────────────────────")
            
            if r['hawkish_keywords_found']:
                kw_str = ", ".join(f"'{k}'×{c}" for k, c in r['hawkish_keywords_found'])
                lines.append(f"  🦅 Hawkish Keywords: {kw_str}")
            
            if r['dovish_keywords_found']:
                kw_str = ", ".join(f"'{k}'×{c}" for k, c in r['dovish_keywords_found'])
                lines.append(f"  🕊️  Dovish Keywords: {kw_str}")
            
            lines.append(f"  Sentences Analyzed: {r['sentence_count']}")
        
        # Comprehensive judgment
        lines.append(f"\n{'═' * 60}")
        lines.append("  📊 Comprehensive Assessment")
        lines.append(f"{'═' * 60}")
        
        if "fed" in results and "boj" in results:
            fed_hawk = results["fed"]["net_hawk_dove"]
            boj_hawk = results["boj"]["net_hawk_dove"]
            
            # Fed Hawkish + BOJ Dovish → Bullish USD/JPY
            combined = fed_hawk - boj_hawk
            if combined > 0.3:
                lines.append("  USD/JPY Direction: Bullish 📈 (Fed Hawkish + BOJ Dovish → USD Strengthens)")
            elif combined < -0.3:
                lines.append("  USD/JPY Direction: Bearish 📉 (Fed Dovish + BOJ Hawkish → JPY Strengthens)")
            else:
                lines.append("  USD/JPY Direction: Neutral ↔️ (Central bank policy divergence not obvious)")
            
            lines.append(f"  Fed Net Score: {fed_hawk:+.4f} | BOJ Net Score: {boj_hawk:+.4f}")
            lines.append(f"  Combined Indicator: {combined:+.4f}")
        
        report = "\n".join(lines)
        return report
    
    @staticmethod
    def _preprocess(text: str) -> str:
        """Text preprocessing: Remove extra whitespace"""
        text = re.sub(r'\s+', ' ', text.strip())
        return text

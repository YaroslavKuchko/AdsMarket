"""
AI-powered channel analytics using OpenAI/OpenRouter.

Generates insights, recommendations, and content strategy suggestions.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import settings
from app.db.models import Channel, ChannelPost, ChannelStats

logger = logging.getLogger(__name__)

# JSON response schema for AI
AI_INSIGHTS_SCHEMA = {
    "category": "string - категория канала",
    "targetAudience": "string - описание целевой аудитории",
    "rating": {
        "score": "number 1-10",
        "explanation": "string - объяснение оценки"
    },
    "strengths": ["string - сильная сторона 1", "..."],
    "weaknesses": ["string - зона роста 1", "..."],
    "growthForecast": {
        "subscribers30d": "string - прогноз",
        "percentage": "string - процент",
        "explanation": "string - обоснование"
    },
    "advertisingRecommendation": {
        "whyBuyAds": "string - почему покупать рекламу",
        "bestFor": ["string - тип бизнеса"],
        "audienceQuality": "высокая/средняя/низкая"
    },
    "contentTips": ["string - рекомендация"]
}


class AIAnalytics:
    """
    AI-powered analytics for Telegram channels.
    
    Supports both OpenAI and OpenRouter APIs.
    """
    
    def __init__(self):
        self.client = None
        self.model = None
        self._initialized = False
    
    def _init_client(self):
        """Initialize OpenAI client lazily."""
        if self._initialized:
            return True
        
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not configured")
            return False
        
        try:
            from openai import OpenAI
            
            # Detect API type based on key prefix
            if settings.openai_api_key.startswith("sk-or-"):
                # OpenRouter API
                self.client = OpenAI(
                    api_key=settings.openai_api_key,
                    base_url="https://openrouter.ai/api/v1",
                )
                self.model = "openai/gpt-4o-mini"
            else:
                # Standard OpenAI API
                self.client = OpenAI(api_key=settings.openai_api_key)
                self.model = "gpt-4o-mini"
            
            self._initialized = True
            logger.info(f"AI client initialized with model: {self.model}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize AI client: {e}")
            return False
    
    def calculate_metrics(
        self,
        db: Session,
        channel: Channel,
        days_back: int = 30,
    ) -> Dict[str, Any]:
        """Calculate channel metrics from posts."""
        # Get posts
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        posts = db.query(ChannelPost).filter(
            ChannelPost.channel_id == channel.id,
            ChannelPost.date >= cutoff,
        ).all()
        
        if not posts:
            return {}
        
        subscribers = channel.subscriber_count or 1
        
        # Calculate metrics
        total_views = sum(p.views or 0 for p in posts)
        total_reactions = sum(p.reactions_count or 0 for p in posts)
        total_forwards = sum(p.forwards or 0 for p in posts)
        total_replies = sum(p.replies or 0 for p in posts)
        
        avg_views = total_views // len(posts)
        avg_engagement = (total_reactions + total_forwards + total_replies) / len(posts)
        engagement_rate = (avg_engagement / subscribers) * 100
        
        # Best performing posts
        sorted_posts = sorted(posts, key=lambda p: p.reactions_count or 0, reverse=True)
        best_posts = []
        for p in sorted_posts[:5]:
            best_posts.append({
                "message_id": p.message_id,
                "text": (p.text[:100] + "...") if p.text and len(p.text) > 100 else p.text,
                "date": p.date.strftime("%Y-%m-%d %H:%M") if p.date else None,
                "views": p.views,
                "reactions": p.reactions_count,
                "forwards": p.forwards,
            })
        
        # Media distribution
        media_counts = {}
        for p in posts:
            if p.media_type:
                media_counts[p.media_type] = media_counts.get(p.media_type, 0) + 1
        
        # Calculate trends
        views_by_day = {}
        for p in posts:
            if p.date:
                day = p.date.strftime("%Y-%m-%d")
                views_by_day[day] = views_by_day.get(day, 0) + (p.views or 0)
        
        views_trend = "stable"
        if len(views_by_day) >= 7:
            days = sorted(views_by_day.keys())
            first_week = sum(views_by_day.get(d, 0) for d in days[:7])
            last_week = sum(views_by_day.get(d, 0) for d in days[-7:])
            if last_week > first_week * 1.1:
                views_trend = "increasing"
            elif last_week < first_week * 0.9:
                views_trend = "decreasing"
        
        return {
            "total_posts": len(posts),
            "avg_views": avg_views,
            "avg_engagement_rate": round(engagement_rate, 2),
            "total_reactions": total_reactions,
            "total_forwards": total_forwards,
            "total_replies": total_replies,
            "best_post_views": max(p.views or 0 for p in posts),
            "posts_with_media": len([p for p in posts if p.media_type]),
            "media_distribution": media_counts,
            "best_posts": best_posts,
            "views_trend": views_trend,
        }
    
    async def generate_insights(
        self,
        db: Session,
        channel: Channel,
        days_back: int = 30,
    ) -> str:
        """Generate AI-powered insights for a channel."""
        if not self._init_client():
            return "AI analytics not configured. Set OPENAI_API_KEY in .env"
        
        try:
            # Get metrics
            metrics = self.calculate_metrics(db, channel, days_back)
            if not metrics:
                return "No data available for analysis"
            
            # Get channel stats
            stats = db.query(ChannelStats).filter(
                ChannelStats.channel_id == channel.id
            ).first()
            
            # Build prompt
            prompt = f"""
Analyze this Telegram channel data and provide actionable insights:

Channel: @{channel.username}
Title: {channel.title}
Subscribers: {channel.subscriber_count:,}

Key Metrics (last {days_back} days):
- Total posts: {metrics.get('total_posts', 0)}
- Average views: {metrics.get('avg_views', 0):,}
- Average engagement rate: {metrics.get('avg_engagement_rate', 0):.2f}%
- Total reactions: {metrics.get('total_reactions', 0):,}
- Total forwards: {metrics.get('total_forwards', 0):,}
- Total replies: {metrics.get('total_replies', 0):,}

Trends:
- Views trend: {metrics.get('views_trend', 'stable')}
- Subscriber growth 7d: {stats.subscriber_growth_7d if stats else 0:+,}
- Subscriber growth 30d: {stats.subscriber_growth_30d if stats else 0:+,}

Content Analysis:
- Media distribution: {metrics.get('media_distribution', {})}
- Posts with media: {metrics.get('posts_with_media', 0)}

Best performing posts:
{json.dumps(metrics.get('best_posts', []), indent=2, ensure_ascii=False)}

Please provide:
1. Key insights about channel performance (2-3 points)
2. Recommendations for improvement (2-3 points)
3. Content strategy suggestions (2-3 points)
4. Engagement optimization tips (2-3 points)

Keep the response concise and actionable. Use bullet points.
"""
            
            # Call AI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты эксперт по аналитике Telegram-каналов. Отвечай на русском языке, давай конкретные и полезные рекомендации для владельца канала. Используй маркированные списки для структурирования ответа.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=800,
                temperature=0.7,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating AI insights: {e}")
            return f"Error generating insights: {str(e)}"
    
    async def generate_content_suggestions(
        self,
        db: Session,
        channel: Channel,
    ) -> str:
        """Generate content suggestions based on best performing posts."""
        if not self._init_client():
            return "AI analytics not configured"
        
        try:
            # Get best posts
            posts = db.query(ChannelPost).filter(
                ChannelPost.channel_id == channel.id,
            ).order_by(ChannelPost.reactions_count.desc()).limit(10).all()
            
            if not posts:
                return "No posts available for analysis"
            
            posts_data = []
            for p in posts:
                posts_data.append({
                    "text": p.text[:500] if p.text else "",
                    "views": p.views,
                    "reactions": p.reactions_count,
                    "media_type": p.media_type,
                })
            
            prompt = f"""
Based on the best performing posts from @{channel.username}, suggest content ideas:

Top posts:
{json.dumps(posts_data, indent=2, ensure_ascii=False)}

Generate 5 content ideas that would perform well based on these patterns.
For each idea, explain why it would work based on the data.
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты креативный контент-стратег для Telegram-каналов. Отвечай на русском языке.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
                temperature=0.8,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating content suggestions: {e}")
            return f"Error: {str(e)}"


    async def generate_structured_insights(
        self,
        db: Session,
        channel: Channel,
    ) -> Dict[str, Any]:
        """
        Generate structured AI insights with JSON response.
        
        Returns parsed JSON with category, rating, recommendations, etc.
        """
        if not self._init_client():
            return {"error": "AI analytics not configured. Set OPENAI_API_KEY in .env"}
        
        try:
            # Get channel stats
            stats = db.query(ChannelStats).filter(
                ChannelStats.channel_id == channel.id
            ).first()
            
            if not stats:
                return {"error": "No statistics available for this channel"}
            
            # Get top 3 posts by views
            top_posts = db.query(ChannelPost).filter(
                ChannelPost.channel_id == channel.id
            ).order_by(desc(ChannelPost.views)).limit(3).all()
            
            # Format top posts for prompt
            posts_text = ""
            for i, post in enumerate(top_posts, 1):
                text = (post.full_text or post.text_preview or "")[:300]
                posts_text += f"{i}. {text}\n   👁 {post.views} просмотров | ❤️ {post.reactions} реакций\n\n"
            
            if not posts_text:
                posts_text = "Нет данных о постах"
            
            # Calculate growth percentage
            growth_percent = 0
            if stats.subscriber_count and stats.subscriber_growth_30d:
                prev_count = stats.subscriber_count - stats.subscriber_growth_30d
                if prev_count > 0:
                    growth_percent = round((stats.subscriber_growth_30d / prev_count) * 100, 1)
            
            # Build the prompt
            prompt = f"""Ты — эксперт по аналитике Telegram-каналов и рекламе. Проанализируй канал на основе данных.

**Данные канала:**
- Название: {channel.title}
- Username: @{channel.username}
- Описание: {channel.description or 'Не указано'}
- Подписчики: {stats.subscriber_count:,}
- Рост за 30 дней: {stats.subscriber_growth_30d:+,} ({growth_percent:+}%)
- Средние просмотры: {stats.avg_post_views:,}
- Вовлечённость (ER): {stats.engagement_rate or 0}%
- Постов в день: {float(stats.avg_posts_per_day or 0):.1f}
- Динамика: {stats.dynamics or 'стабильно'}

**Метрики вовлечённости:**
- Реакции: {stats.avg_reactions or 0}/пост
- Комментарии: {stats.avg_comments or 0}/пост
- Репосты: {stats.avg_shares or 0}/пост

**Топ-3 популярных поста:**
{posts_text}

**Задание:**
Проанализируй канал и ответь СТРОГО в формате JSON (без markdown, без ```):

{{
  "category": "определи категорию канала (Новости, Технологии, Бизнес, Криптовалюты, Маркетинг, Развлечения, Образование, Лайфстайл, Скидки и промокоды, или другая)",
  "targetAudience": "опиши целевую аудиторию канала одним предложением (возраст, интересы)",
  "rating": {{
    "score": число от 1 до 10,
    "explanation": "краткое объяснение оценки в 1-2 предложения"
  }},
  "strengths": [
    "сильная сторона 1",
    "сильная сторона 2",
    "сильная сторона 3"
  ],
  "weaknesses": [
    "зона роста 1",
    "зона роста 2",
    "зона роста 3"
  ],
  "growthForecast": {{
    "subscribers30d": "+XXX подписчиков",
    "percentage": "+X%",
    "explanation": "краткое обоснование прогноза"
  }},
  "advertisingRecommendation": {{
    "whyBuyAds": "почему рекламодателю стоит покупать рекламу на этом канале (2-3 предложения)",
    "bestFor": ["тип бизнеса 1", "тип бизнеса 2", "тип бизнеса 3"],
    "audienceQuality": "высокая" или "средняя" или "низкая"
  }},
  "contentTips": [
    "рекомендация по контенту 1",
    "рекомендация по контенту 2"
  ]
}}

Отвечай ТОЛЬКО валидным JSON, без дополнительного текста, без markdown. Все значения на русском языке."""

            # Call AI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты эксперт по аналитике Telegram-каналов. Отвечай ТОЛЬКО валидным JSON без markdown форматирования.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1000,
                temperature=0.7,
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Clean up response - remove markdown if present
            if response_text.startswith("```"):
                # Remove ```json and ``` wrappers
                response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
                response_text = re.sub(r'\s*```$', '', response_text)
            
            # Parse JSON
            try:
                result = json.loads(response_text)
                result["success"] = True
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Response was: {response_text[:500]}")
                return {
                    "error": "Failed to parse AI response",
                    "raw_response": response_text[:500]
                }
            
        except Exception as e:
            logger.error(f"Error generating structured insights: {e}")
            return {"error": str(e)}


# Global instance
ai_analytics = AIAnalytics()


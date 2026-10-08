import { GoogleGenerativeAI } from '@google/generative-ai';

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);

const LEAD_EXTRACTION_PROMPT = `You are a lead extraction AI. Extract structured lead information from the following web page content.

STRICT RULES:
- Only extract information that is ACTUALLY VISIBLE in the content.
- DO NOT guess, infer, or generate email addresses.
- DO NOT invent phone numbers, company names, or budgets.
- If information is not visible, return null for strings or [] for arrays.
- Email must be a real, visible email address in the content.

Return ONLY valid JSON with exactly this structure (no markdown, no explanation):
{
  "full_name": null,
  "company_name": null,
  "email": null,
  "phone": null,
  "website": null,
  "location": null,
  "project_title": null,
  "project_description": null,
  "technologies": [],
  "services_required": [],
  "budget": null,
  "currency": null,
  "timeline": null,
  "lead_type": null,
  "source_title": null,
  "posted_date": null,
  "contact_method": null,
  "lead_quality": "MEDIUM",
  "ai_reason": null
}

lead_quality must be: HIGH, MEDIUM, or LOW based on:
- HIGH: Clear budget, specific requirements, direct contact info
- MEDIUM: Some details available, project is clear
- LOW: Vague requirements, no budget, no contact info`;

export async function extractLeadWithGemini({ url, source_platform, content, title }: {
  url: string;
  source_platform: string;
  content: string;
  title: string;
}) {
  try {
    const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });

    const prompt = `${LEAD_EXTRACTION_PROMPT}

SOURCE URL: ${url}
SOURCE PLATFORM: ${source_platform}
PAGE TITLE: ${title}

PAGE CONTENT:
${content.substring(0, 8000)}`;

    const result = await model.generateContent(prompt);
    const text = result.response.text().trim();

    // Clean response - remove markdown if present
    const cleanText = text
      .replace(/```json\n?/g, '')
      .replace(/```\n?/g, '')
      .trim();

    const lead = JSON.parse(cleanText);

    return { success: true, lead };
  } catch (error: any) {
    console.error('[GEMINI] Extraction failed:', error);
    return { success: false, error: error.message };
  }
}

'use client';

import React, { useState, useMemo } from 'react';
import {
  LayoutDashboard,
  Search,
  Filter,
  DollarSign,
  TrendingUp,
  Award,
  Sparkles,
  Mail,
  MessageCircle,
  Phone,
  ArrowRight,
  ArrowLeft,
  ChevronRight,
  ExternalLink,
  Bot,
  Copy,
  Check,
  X,
  Flame,
  Calendar,
  Building,
  UserCheck
} from 'lucide-react';
import { patchLeadStatus, fetchBdePitch } from '../lib/api';

const STAGES = [
  { id: 'NEW', label: 'New Leads', icon: '📥', color: 'border-slate-500/30 bg-slate-500/5' },
  { id: 'CONTACTED', label: 'Outreach Sent', icon: '📤', color: 'border-blue-500/30 bg-blue-500/5' },
  { id: 'REPLIED', label: 'Replied & Warm', icon: '💬', color: 'border-amber-500/30 bg-amber-500/5' },
  { id: 'MEETING', label: 'Meeting Scheduled', icon: '📅', color: 'border-purple-500/30 bg-purple-500/5' },
  { id: 'PROPOSAL', label: 'Proposal / Trial', icon: '📝', color: 'border-indigo-500/30 bg-indigo-500/5' },
  { id: 'WON', label: 'Closed Won', icon: '🏆', color: 'border-emerald-500/30 bg-emerald-500/5' }
];

function estimateDealValue(lead) {
  const desc = ((lead.description || '') + ' ' + (lead.ai_requirement || '') + ' ' + (lead.ai_tech_stack || '')).lower();
  if (desc.includes('maintenance') || desc.includes('speed') || desc.includes('amc')) {
    return { label: 'Part-Time Retainer', amount: 36000, display: '₹36,000/mo' };
  }
  if (desc.includes('crm') || desc.includes('mobile') || desc.includes('full time') || desc.includes('dedicated')) {
    return { label: 'Full-Time Dedicated', amount: 72000, display: '₹72,000/mo' };
  }
  return { label: 'Dedicated Developer', amount: 36000, display: '₹450/hr (~₹36k/mo)' };
}

export default function PipelineKanban({ leads = [], onLeadUpdate, onWhatsApp, onEmail, notify }) {
  const [search, setSearch] = useState('');
  const [serviceFilter, setServiceFilter] = useState('ALL');
  const [bdeModalLead, setBdeModalLead] = useState(null);
  const [bdePitchData, setBdePitchData] = useState(null);
  const [bdeLoading, setBdeLoading] = useState(false);
  const [copiedPitch, setCopiedPitch] = useState(false);
  const [activeTabPitch, setActiveTabPitch] = useState('email');

  // Filter leads by search & service
  const filteredLeads = useMemo(() => {
    return leads.filter(l => {
      const q = search.toLowerCase();
      const comp = (l.company_name || l['Company Name'] || '').toLowerCase();
      const tech = (l.ai_tech_stack || l.lead_type || '').toLowerCase();
      const desc = (l.description || '').toLowerCase();

      const matchesSearch = !q || comp.includes(q) || tech.includes(q) || desc.includes(q);

      if (!matchesSearch) return false;
      if (serviceFilter === 'ALL') return true;
      if (serviceFilter === 'MAINTENANCE') return desc.includes('maintenance') || desc.includes('speed') || desc.includes('amc');
      if (serviceFilter === 'CRM') return desc.includes('crm') || desc.includes('erp') || desc.includes('portal');
      if (serviceFilter === 'MOBILE') return desc.includes('mobile') || desc.includes('flutter') || desc.includes('react native') || desc.includes('app');
      if (serviceFilter === 'WEB') return desc.includes('laravel') || desc.includes('next') || desc.includes('php') || desc.includes('node');
      return true;
    });
  }, [leads, search, serviceFilter]);

  // Group leads into stages
  const columns = useMemo(() => {
    const map = {
      NEW: [],
      CONTACTED: [],
      REPLIED: [],
      MEETING: [],
      PROPOSAL: [],
      WON: []
    };

    filteredLeads.forEach(l => {
      const rawStatus = (l.status || l.Status || 'NEW').toUpperCase().trim();
      let stageKey = 'NEW';
      if (rawStatus === 'CONTACTED' || rawStatus === 'EMAIL_SENT') stageKey = 'CONTACTED';
      else if (rawStatus === 'REPLIED') stageKey = 'REPLIED';
      else if (rawStatus === 'MEETING') stageKey = 'MEETING';
      else if (rawStatus === 'PROPOSAL') stageKey = 'PROPOSAL';
      else if (rawStatus === 'WON') stageKey = 'WON';
      else if (rawStatus === 'LOST' || rawStatus === 'DISQUALIFIED') return; // hide lost from active board
      else stageKey = 'NEW';

      map[stageKey].push(l);
    });

    return map;
  }, [filteredLeads]);

  // Pipeline metrics
  const metrics = useMemo(() => {
    let pipelineValue = 0;
    let wonRevenue = 0;
    let activeDeals = 0;

    STAGES.forEach(st => {
      const stageLeads = columns[st.id] || [];
      stageLeads.forEach(l => {
        const est = estimateDealValue(l);
        if (st.id === 'WON') {
          wonRevenue += est.amount;
        } else {
          pipelineValue += est.amount;
          activeDeals++;
        }
      });
    });

    return {
      activeDeals,
      pipelineValue: pipelineValue.toLocaleString('en-IN'),
      wonRevenue: wonRevenue.toLocaleString('en-IN')
    };
  }, [columns]);

  const handleStageMove = async (lead, targetStage) => {
    const leadId = lead.id || lead.lead_id || lead['\ufefflead_id'];
    try {
      await patchLeadStatus(leadId, targetStage);
      if (notify) notify(`Moved ${lead.company_name || 'deal'} to ${targetStage}`, 'success');
      if (onLeadUpdate) onLeadUpdate();
    } catch (err) {
      if (notify) notify(`Failed to update deal stage: ${err.message}`, 'error');
    }
  };

  const openBdeModal = async (lead) => {
    setBdeModalLead(lead);
    setBdeLoading(true);
    setBdePitchData(null);
    try {
      const res = await fetchBdePitch(lead);
      setBdePitchData(res);
    } catch (err) {
      if (notify) notify(`AI BDE error: ${err.message}`, 'error');
    } finally {
      setBdeLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedPitch(true);
    setTimeout(() => setCopiedPitch(false), 2000);
    if (notify) notify('Pitch copied to clipboard!', 'info');
  };

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* 1. Executive CRM Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/70 backdrop-blur shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md">
              <LayoutDashboard size={20} />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                Sangeeta Infotech B2B Sales CRM
                <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                  Autonomous Deal Pipeline
                </span>
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Track active deals, forecast monthly retainers, and close dedicated developer contracts.
              </p>
            </div>
          </div>
        </div>

        {/* Financial KPIs */}
        <div className="flex items-center gap-3">
          <div className="px-4 py-2 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-700/60">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Active Deals</div>
            <div className="text-lg font-bold text-slate-800 dark:text-slate-100">{metrics.activeDeals}</div>
          </div>

          <div className="px-4 py-2 rounded-xl bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-200/50 dark:border-indigo-800/40">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-indigo-500">Pipeline Value</div>
            <div className="text-lg font-bold text-indigo-600 dark:text-indigo-400">₹{metrics.pipelineValue}</div>
          </div>

          <div className="px-4 py-2 rounded-xl bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-200/50 dark:border-emerald-800/40">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">Won Revenue</div>
            <div className="text-lg font-bold text-emerald-600 dark:text-emerald-400">₹{metrics.wonRevenue}</div>
          </div>
        </div>
      </div>

      {/* 2. Search & Category Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <div className="relative flex-1 min-w-[260px] max-w-md">
          <Search className="absolute left-3 top-2.5 text-slate-400" size={16} />
          <input
            type="text"
            placeholder="Search deals by company, tech stack, or requirements..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm"
          />
        </div>

        <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl text-xs font-medium">
          {[
            { id: 'ALL', label: 'All Deals' },
            { id: 'WEB', label: 'Laravel / Web' },
            { id: 'MAINTENANCE', label: 'AMC & Speed' },
            { id: 'CRM', label: 'CRM / ERP' },
            { id: 'MOBILE', label: 'Mobile Apps' }
          ].map(f => (
            <button
              key={f.id}
              onClick={() => setServiceFilter(f.id)}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                serviceFilter === f.id
                  ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* 3. 6-Stage Kanban Board */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 flex-1 overflow-x-auto pb-4">
        {STAGES.map((st, sIndex) => {
          const stageLeads = columns[st.id] || [];
          return (
            <div
              key={st.id}
              className={`flex flex-col rounded-2xl border ${st.color} backdrop-blur-sm min-w-[240px] max-h-[calc(100vh-280px)] overflow-hidden`}
            >
              {/* Column Header */}
              <div className="p-3 border-b border-slate-200/50 dark:border-slate-800/50 flex items-center justify-between bg-white/40 dark:bg-slate-900/40">
                <div className="flex items-center gap-2">
                  <span className="text-base">{st.icon}</span>
                  <span className="text-xs font-bold text-slate-800 dark:text-slate-200">{st.label}</span>
                </div>
                <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-slate-200/60 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                  {stageLeads.length}
                </span>
              </div>

              {/* Cards Container */}
              <div className="p-2 space-y-2.5 overflow-y-auto flex-1">
                {stageLeads.length === 0 ? (
                  <div className="h-28 flex items-center justify-center text-[11px] text-slate-400 border border-dashed border-slate-300/40 dark:border-slate-800/60 rounded-xl">
                    No active deals
                  </div>
                ) : (
                  stageLeads.map(lead => {
                    const compName = lead.company_name || lead['Company Name'] || 'Prospective Client';
                    const est = estimateDealValue(lead);
                    const score = parseFloat(lead.ai_score || lead.intent_score || 5);
                    const phone = lead.mobile_number || lead['Mobile Number'];
                    const email = lead.email || lead['Email'];
                    const tech = lead.ai_tech_stack || lead.lead_type || 'Software Engineering';

                    return (
                      <div
                        key={lead.id || lead.lead_id}
                        className="group relative p-3 rounded-xl bg-white dark:bg-slate-900/90 border border-slate-200/80 dark:border-slate-800 shadow-sm hover:shadow-md transition-all space-y-2.5"
                      >
                        {/* Company & Score */}
                        <div className="flex items-start justify-between gap-1">
                          <h4 className="text-xs font-bold text-slate-900 dark:text-white line-clamp-1 group-hover:text-indigo-600 dark:group-hover:text-indigo-400">
                            {compName}
                          </h4>
                          {score >= 8 && (
                            <span className="flex items-center gap-0.5 text-[10px] font-bold text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded">
                              <Flame size={10} /> {score}
                            </span>
                          )}
                        </div>

                        {/* Tech Tag & Retainer Value */}
                        <div className="flex items-center justify-between gap-1 text-[11px]">
                          <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-medium line-clamp-1 max-w-[130px]">
                            {tech}
                          </span>
                          <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
                            {est.display}
                          </span>
                        </div>

                        {/* Contact Buttons & AI BDE */}
                        <div className="pt-1.5 border-t border-slate-100 dark:border-slate-800/60 flex items-center justify-between">
                          <div className="flex items-center gap-1">
                            {email && (
                              <button
                                onClick={() => onEmail ? onEmail(lead) : window.open(`mailto:${email}`)}
                                title="Send Email"
                                className="p-1 rounded-md text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/40"
                              >
                                <Mail size={13} />
                              </button>
                            )}

                            {phone && (
                              <button
                                onClick={() => {
                                  if (onWhatsApp) onWhatsApp(lead);
                                  else {
                                    const clean = phone.replace(/[^\d]/g, '');
                                    window.open(`https://wa.me/${clean}?text=Hi%20${encodeURIComponent(compName)}`);
                                  }
                                }}
                                title="Open WhatsApp"
                                className="p-1 rounded-md text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/40"
                              >
                                <MessageCircle size={13} />
                              </button>
                            )}

                            <button
                              onClick={() => openBdeModal(lead)}
                              title="Generate AI BDE Pitch"
                              className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-gradient-to-r from-indigo-500 to-purple-500 text-white text-[10px] font-bold shadow-xs hover:opacity-90"
                            >
                              <Bot size={11} /> Pitch
                            </button>
                          </div>

                          {/* Stage Progressor Controls */}
                          <div className="flex items-center gap-0.5">
                            {sIndex > 0 && (
                              <button
                                onClick={() => handleStageMove(lead, STAGES[sIndex - 1].id)}
                                title={`Move back to ${STAGES[sIndex - 1].label}`}
                                className="p-1 rounded text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                              >
                                <ArrowLeft size={11} />
                              </button>
                            )}
                            {sIndex < STAGES.length - 1 && (
                              <button
                                onClick={() => handleStageMove(lead, STAGES[sIndex + 1].id)}
                                title={`Advance to ${STAGES[sIndex + 1].label}`}
                                className="p-1 rounded text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                              >
                                <ArrowRight size={11} />
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 4. AI BDE Pitch Modal */}
      {bdeModalLead && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="relative w-full max-w-2xl rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center text-white">
                  <Bot size={18} />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900 dark:text-white">
                    AI BDE Pitch for {bdeModalLead.company_name || 'Client'}
                  </h3>
                  <p className="text-xs text-slate-500">Autonomous Deal Closer for Sangeeta Infotech</p>
                </div>
              </div>
              <button
                onClick={() => setBdeModalLead(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
              >
                <X size={18} />
              </button>
            </div>

            {bdeLoading ? (
              <div className="py-16 flex flex-col items-center justify-center gap-2 text-slate-400 text-xs">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                Analyzing tech stack and crafting winning deal pitch...
              </div>
            ) : bdePitchData ? (
              <div className="space-y-4">
                {/* Proposal Strategy Card */}
                <div className="grid grid-cols-2 gap-2 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/60 dark:border-slate-700/60 text-xs">
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Recommended Package</span>
                    <span className="font-bold text-emerald-600 dark:text-emerald-400">{bdePitchData.recommended_package}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Risk Reversal</span>
                    <span className="font-bold text-indigo-600 dark:text-indigo-400">{bdePitchData.trial_offer}</span>
                  </div>
                </div>

                {/* Pitch Channel Tabs */}
                <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
                  <button
                    onClick={() => setActiveTabPitch('email')}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 ${
                      activeTabPitch === 'email'
                        ? 'bg-blue-600 text-white shadow-xs'
                        : 'text-slate-500 hover:text-slate-800 dark:hover:text-white'
                    }`}
                  >
                    <Mail size={13} /> Cold Email Pitch
                  </button>
                  <button
                    onClick={() => setActiveTabPitch('whatsapp')}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 ${
                      activeTabPitch === 'whatsapp'
                        ? 'bg-emerald-600 text-white shadow-xs'
                        : 'text-slate-500 hover:text-slate-800 dark:hover:text-white'
                    }`}
                  >
                    <MessageCircle size={13} /> WhatsApp Pitch
                  </button>
                </div>

                {/* Pitch Content Box */}
                <div className="relative p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono whitespace-pre-wrap leading-relaxed text-slate-800 dark:text-slate-200">
                  {activeTabPitch === 'email' ? (
                    <div>
                      <div className="font-bold text-slate-500 pb-2 border-b border-slate-200 dark:border-slate-800 mb-2">
                        Subject: {bdePitchData.email_pitch?.subject}
                      </div>
                      {bdePitchData.email_pitch?.body}
                    </div>
                  ) : (
                    bdePitchData.whatsapp_pitch?.body
                  )}

                  <button
                    onClick={() =>
                      copyToClipboard(
                        activeTabPitch === 'email'
                          ? `Subject: ${bdePitchData.email_pitch?.subject}\n\n${bdePitchData.email_pitch?.body}`
                          : bdePitchData.whatsapp_pitch?.body
                      )
                    }
                    className="absolute top-3 right-3 px-2.5 py-1 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold flex items-center gap-1 shadow-xs hover:bg-slate-50"
                  >
                    {copiedPitch ? <Check size={13} className="text-emerald-500" /> : <Copy size={13} />}
                    {copiedPitch ? 'Copied' : 'Copy'}
                  </button>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    onClick={() => setBdeModalLead(null)}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    Close
                  </button>
                  <button
                    onClick={() => {
                      if (activeTabPitch === 'email' && onEmail) {
                        onEmail(bdeModalLead);
                      } else if (activeTabPitch === 'whatsapp' && onWhatsApp) {
                        onWhatsApp(bdeModalLead);
                      }
                      setBdeModalLead(null);
                    }}
                    className="px-4 py-2 rounded-xl text-xs font-bold bg-indigo-600 text-white hover:bg-indigo-700 shadow-md flex items-center gap-1.5"
                  >
                    Send to Client Now <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-xs text-rose-500 py-6 text-center">Failed to load BDE pitch.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  Gift,
  Share2,
  Calendar,
  Image as ImageIcon,
  Video,
  Send,
  CheckCircle2,
  Phone,
  Mail,
  Copy,
  Plus,
  ExternalLink,
  Download,
  Clock,
  Building,
  User,
  MapPin,
  RefreshCw,
  Search
} from 'lucide-react';
import {
  fetchFestivalOffers,
  fetchFestivalClients,
  saveFestivalClient,
  fetchFestivalOfferPitch,
  fetchFestivalCreative,
  fetchFestivalSchedules,
  scheduleFestivalDispatch,
  fetchBdeStrategy
} from '../lib/api';

export default function OffersAndCreatives({ leads = [], onEmail, onWhatsApp, notify }) {
  const [activeSubTab, setActiveSubTab] = useState('pitch'); // 'pitch', 'clients', 'studio', 'schedules'
  const [offersData, setOffersData] = useState(null);
  const [clients, setClients] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);

  // Outreach / Pitch state
  const [leadSearch, setLeadSearch] = useState('');
  const [selectedLead, setSelectedLead] = useState(null);
  const [pitchData, setPitchData] = useState(null);
  const [generatingPitch, setGeneratingPitch] = useState(false);

  // Client Onboarding Form state
  const [showClientModal, setShowClientModal] = useState(false);
  const [clientForm, setClientForm] = useState({
    business_name: '',
    owner_name: '',
    phone: '',
    email: '',
    tagline: 'Quality Products & Dedicated Services',
    address: 'Ahmedabad, Gujarat',
    website: 'info@sangeetainfotech.co.in',
    pack: 'fest_10_pack',
    paid_amount: 500,
    status: 'PAID_ACTIVE'
  });

  // Creative Studio state
  const [selectedFestival, setSelectedFestival] = useState('diwali_new_year');
  const [studioClient, setStudioClient] = useState({
    business_name: 'Shreeji Jewellers',
    tagline: 'Exclusive Gold & Diamond Jewellery',
    phone: '+91 9106060400',
    address: 'CG Road, Ahmedabad',
    website: 'info@sangeetainfotech.co.in'
  });
  const [generatedSvg, setGeneratedSvg] = useState('');
  const [isRenderingSvg, setIsRenderingSvg] = useState(false);
  const canvasRef = useRef(null);

  // Load initial data
  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const [resOffers, resClients, resSched] = await Promise.all([
        fetchFestivalOffers().catch(() => ({})),
        fetchFestivalClients().catch(() => ({ clients: [] })),
        fetchFestivalSchedules().catch(() => ({ schedules: [] }))
      ]);

      if (resOffers && resOffers.success) {
        setOffersData(resOffers);
      }
      if (resClients && resClients.clients) {
        setClients(resClients.clients);
        if (resClients.clients.length > 0) {
          setStudioClient(resClients.clients[0]);
        }
      }
      if (resSched && resSched.schedules) {
        setSchedules(resSched.schedules);
      }
    } catch (err) {
      console.error('Failed to load offers data:', err);
    } finally {
      setLoading(false);
    }
  }

  // Generate Creative when Studio params change
  useEffect(() => {
    async function renderCreative() {
      setIsRenderingSvg(true);
      try {
        const res = await fetchFestivalCreative(studioClient, selectedFestival);
        if (res && res.svg) {
          setGeneratedSvg(res.svg);
        }
      } catch (err) {
        console.error('Failed to generate creative SVG:', err);
      } finally {
        setIsRenderingSvg(false);
      }
    }
    if (activeSubTab === 'studio') {
      renderCreative();
    }
  }, [selectedFestival, studioClient, activeSubTab]);

  // Handle lead selection for pitch
  async function handleSelectLeadForPitch(l) {
    setSelectedLead(l);
    setGeneratingPitch(true);
    try {
      const res = await fetchFestivalOfferPitch(l);
      if (res && res.pitch) {
        setPitchData(res.pitch);
      }
    } catch (e) {
      if (notify) notify('Failed to generate pitch: ' + e.message, 'error');
    } finally {
      setGeneratingPitch(false);
    }
  }

  // Handle client onboarding submit
  async function handleSaveClient(e) {
    e.preventDefault();
    try {
      const res = await saveFestivalClient(clientForm);
      if (res && res.success) {
        if (notify) notify(`Enrolled client ${clientForm.business_name} successfully!`, 'success');
        setShowClientModal(false);
        setClientForm({
          business_name: '',
          owner_name: '',
          phone: '',
          email: '',
          tagline: 'Quality Products & Dedicated Services',
          address: 'Ahmedabad, Gujarat',
          website: 'info@sangeetainfotech.co.in',
          pack: 'fest_10_pack',
          paid_amount: 500,
          status: 'PAID_ACTIVE'
        });
        loadAll();
      }
    } catch (err) {
      if (notify) notify('Error saving client: ' + err.message, 'error');
    }
  }

  // Schedule dispatch
  async function handleScheduleDispatch(clientId, festivalId) {
    try {
      const res = await scheduleFestivalDispatch(clientId, festivalId);
      if (res && res.success) {
        if (notify) notify('Scheduled festival post dispatch!', 'success');
        loadAll();
      }
    } catch (err) {
      if (notify) notify('Schedule error: ' + err.message, 'error');
    }
  }

  // Download SVG as 1080x1080 PNG via Canvas
  function downloadAsPng() {
    if (!generatedSvg) return;
    const img = new Image();
    const svgBlob = new Blob([generatedSvg], { type: 'image/svg+xml;charset=utf-8' });
    const URL = window.URL || window.webkitURL || window;
    const blobURL = URL.createObjectURL(svgBlob);

    img.onload = () => {
      const canvas = canvasRef.current || document.createElement('canvas');
      canvas.width = 1080;
      canvas.height = 1080;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, 1080, 1080);
      const pngUrl = canvas.toDataURL('image/png');

      const downloadLink = document.createElement('a');
      downloadLink.href = pngUrl;
      downloadLink.download = `${studioClient.business_name || 'brand'}_${selectedFestival}.png`;
      document.body.appendChild(downloadLink);
      downloadLink.click();
      document.body.removeChild(downloadLink);
      URL.revokeObjectURL(blobURL);
      if (notify) notify('HD 1080x1080 Creative Downloaded!', 'success');
    };
    img.src = blobURL;
  }

  function copyToClipboard(text, label = 'Text') {
    navigator.clipboard.writeText(text);
    if (notify) notify(`${label} copied to clipboard!`, 'success');
  }

  const filteredLeads = (leads || [])
    .filter((l) => {
      const query = leadSearch.toLowerCase();
      const name = (l.company_name || l['Company Name'] || l.name || '').toLowerCase();
      const city = (l.city || l.location || '').toLowerCase();
      const phone = (l.phone || l.Phone || '').toLowerCase();
      return name.includes(query) || city.includes(query) || phone.includes(query);
    })
    .slice(0, 15);

  const stats = offersData?.stats || {
    total_clients: clients.length,
    active_clients: clients.filter((c) => c.status === 'PAID_ACTIVE').length,
    total_revenue_inr: clients.reduce((sum, c) => sum + (c.paid_amount || 500), 0),
    total_schedules: schedules.length
  };

  return (
    <div style={{ padding: '4px 0 32px 0' }}>
      {/* Hidden canvas for image export */}
      <canvas ref={canvasRef} style={{ display: 'none' }} width={1080} height={1080} />

      {/* Hero Header */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(234, 88, 12, 0.12) 0%, rgba(147, 51, 234, 0.12) 100%)',
          border: '1px solid rgba(234, 88, 12, 0.3)',
          borderRadius: '16px',
          padding: '24px',
          marginBottom: '24px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.05)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <span
                style={{
                  background: 'linear-gradient(135deg, #f97316, #ea580c)',
                  color: '#fff',
                  padding: '4px 10px',
                  borderRadius: '20px',
                  fontSize: '12px',
                  fontWeight: '700',
                  letterSpacing: '1px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <Gift size={14} /> SANGEETA INFOTECH FESTIVE OFFERS
              </span>
              <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Digital Media & Branding Hub</span>
            </div>
            <h1 style={{ fontSize: '24px', fontWeight: '800', margin: '0 0 6px 0', color: 'var(--text-primary)' }}>
              Festival Creatives & Video Reels Engine
            </h1>
            <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)' }}>
              Acquire clients with irresistible pricing: <strong>₹500 for 10 HD Festival Creatives</strong> or <strong>₹1,000 for 3 Video Reels</strong> with their custom logo & branding.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <button
              onClick={() => setShowClientModal(true)}
              style={{
                background: 'linear-gradient(135deg, #ea580c, #c2410c)',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                padding: '10px 18px',
                fontSize: '13px',
                fontWeight: '600',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: '0 2px 8px rgba(234, 88, 12, 0.3)'
              }}
            >
              <Plus size={16} /> Enroll Paying Client
            </button>
            <button
              onClick={loadAll}
              style={{
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                borderRadius: '8px',
                padding: '10px 14px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <RefreshCw size={15} /> Refresh
            </button>
          </div>
        </div>

        {/* Quick Metrics */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px', marginTop: '20px' }}>
          <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '12px 16px' }}>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Enrolled Clients</div>
            <div style={{ fontSize: '22px', fontWeight: '700', color: '#ea580c' }}>{stats.total_clients || 0}</div>
          </div>
          <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '12px 16px' }}>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Active Deliveries</div>
            <div style={{ fontSize: '22px', fontWeight: '700', color: '#10b981' }}>{stats.active_clients || 0}</div>
          </div>
          <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '12px 16px' }}>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Revenue Collected</div>
            <div style={{ fontSize: '22px', fontWeight: '700', color: '#8b5cf6' }}>₹{(stats.total_revenue_inr || 0).toLocaleString()}</div>
          </div>
          <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '12px 16px' }}>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Scheduled Dispatches</div>
            <div style={{ fontSize: '22px', fontWeight: '700', color: '#3b82f6' }}>{stats.total_schedules || schedules.length}</div>
          </div>
        </div>
      </div>

      {/* Package Offer Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        {/* Card 1: 500 Pack */}
        <div
          style={{
            background: 'var(--bg-card, #fff)',
            border: '2px solid rgba(234, 88, 12, 0.4)',
            borderRadius: '14px',
            padding: '20px',
            position: 'relative',
            boxShadow: '0 4px 12px rgba(0,0,0,0.03)'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
            <span style={{ background: '#ffedd5', color: '#ea580c', padding: '3px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: '700' }}>
              MOST POPULAR
            </span>
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontSize: '26px', fontWeight: '900', color: '#ea580c' }}>₹500</span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}> / one-time</span>
            </div>
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: '700', margin: '0 0 4px 0' }}>Festival Brand Pack</h3>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
            <strong>10 HD Festival Creatives</strong> customized with your logo, phone, address & festive greeting.
          </p>
          <ul style={{ paddingLeft: '18px', margin: '0 0 16px 0', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.7' }}>
            <li>10 Major Indian festivals covered</li>
            <li>Custom company logo & contact info on every post</li>
            <li>Ready for WhatsApp Status & Instagram (1080x1080)</li>
            <li>Auto-delivered on festival morning (8:00 AM)</li>
          </ul>
          <button
            onClick={() => {
              setActiveSubTab('pitch');
              if (notify) notify('Select a lead below to generate the ₹500 Festival Pitch!', 'info');
            }}
            style={{
              width: '100%',
              background: '#ea580c',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '9px 0',
              fontWeight: '600',
              fontSize: '13px',
              cursor: 'pointer'
            }}
          >
            Pitch This Offer (₹500)
          </button>
        </div>

        {/* Card 2: 1000 Pack */}
        <div
          style={{
            background: 'var(--bg-card, #fff)',
            border: '1px solid var(--border-color)',
            borderRadius: '14px',
            padding: '20px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.03)'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
            <span style={{ background: '#ede9fe', color: '#7c3aed', padding: '3px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: '700' }}>
              HIGH ENGAGEMENT
            </span>
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontSize: '26px', fontWeight: '900', color: '#7c3aed' }}>₹1,000</span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}> / one-time</span>
            </div>
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: '700', margin: '0 0 4px 0' }}>Viral Reels Pack</h3>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
            <strong>3 High-Retention Video Reels</strong> for Instagram & WhatsApp Status with trending audio & motion graphics.
          </p>
          <ul style={{ paddingLeft: '18px', margin: '0 0 16px 0', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.7' }}>
            <li>3 Short Video Reels (9:16 vertical format)</li>
            <li>Trending background audio & motion typography</li>
            <li>Company logo & CTA outro included</li>
            <li>High-bitrate MP4 download ready</li>
          </ul>
          <button
            onClick={() => {
              setActiveSubTab('pitch');
              if (notify) notify('Select a lead below to generate the Reels Pitch!', 'info');
            }}
            style={{
              width: '100%',
              background: '#7c3aed',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '9px 0',
              fontWeight: '600',
              fontSize: '13px',
              cursor: 'pointer'
            }}
          >
            Pitch Reels Pack (₹1,000)
          </button>
        </div>

        {/* Card 3: 1299 Combo */}
        <div
          style={{
            background: 'var(--bg-card, #fff)',
            border: '1px solid var(--border-color)',
            borderRadius: '14px',
            padding: '20px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.03)'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
            <span style={{ background: '#dcfce7', color: '#16a34a', padding: '3px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: '700' }}>
              BEST VALUE
            </span>
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontSize: '26px', fontWeight: '900', color: '#16a34a' }}>₹1,299</span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}> / combo</span>
            </div>
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: '700', margin: '0 0 4px 0' }}>Festive Combo Booster</h3>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
            <strong>10 HD Images + 3 Video Reels</strong> + 1 FREE Festive Header Banner for Facebook & LinkedIn.
          </p>
          <ul style={{ paddingLeft: '18px', margin: '0 0 16px 0', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.7' }}>
            <li>Everything in Festival Brand Pack (10 Posts)</li>
            <li>Everything in Viral Reels Pack (3 Reels)</li>
            <li>FREE Company Festive Header Banner</li>
            <li>Priority same-day delivery</li>
          </ul>
          <button
            onClick={() => {
              setActiveSubTab('pitch');
              if (notify) notify('Combo booster pitch ready to dispatch!', 'info');
            }}
            style={{
              width: '100%',
              background: '#16a34a',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '9px 0',
              fontWeight: '600',
              fontSize: '13px',
              cursor: 'pointer'
            }}
          >
            Pitch Combo Booster (₹1,299)
          </button>
        </div>
      </div>

      {/* Sub Tabs Navigation */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '2px solid var(--border-color)', marginBottom: '20px' }}>
        {[
          { id: 'pitch', label: '1. Outreach & Pitches', icon: Send },
          { id: 'clients', label: `2. Enrolled Clients (${clients.length})`, icon: Building },
          { id: 'studio', label: '3. AI Creative Studio & Preview', icon: ImageIcon },
          { id: 'schedules', label: `4. Delivery Schedules (${schedules.length})`, icon: Calendar },
          { id: 'strategy', label: '5. 20-Yr BDE Strategy', icon: Sparkles }
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeSubTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveSubTab(tab.id)}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: active ? '3px solid #ea580c' : '3px solid transparent',
                padding: '10px 16px',
                fontWeight: active ? '700' : '500',
                color: active ? '#ea580c' : 'var(--text-secondary)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '14px',
                marginBottom: '-2px'
              }}
            >
              <Icon size={16} /> {tab.label}
            </button>
          );
        })}
      </div>

      {/* ======================= TAB 1: OUTREACH & PITCH GENERATOR ======================= */}
      {activeSubTab === 'pitch' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: '20px' }}>
          {/* Left: Lead Selection */}
          <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '18px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: '700', margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Search size={16} /> Select Lead to Pitch Offer
            </h3>
            <input
              type="text"
              placeholder="Search by company name, city, phone..."
              value={leadSearch}
              onChange={(e) => setLeadSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: '8px',
                border: '1px solid var(--border-color)',
                marginBottom: '14px',
                fontSize: '13px',
                boxSizing: 'border-box'
              }}
            />

            <div style={{ maxHeight: '460px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {filteredLeads.map((l, idx) => {
                const name = l.company_name || l['Company Name'] || l.name || `Lead #${idx + 1}`;
                const phone = l.phone || l.Phone || l.mobile || '';
                const email = l.email || l.Email || '';
                const isSelected = selectedLead === l;

                return (
                  <div
                    key={idx}
                    onClick={() => handleSelectLeadForPitch(l)}
                    style={{
                      padding: '12px',
                      borderRadius: '8px',
                      border: isSelected ? '2px solid #ea580c' : '1px solid var(--border-color)',
                      background: isSelected ? 'rgba(234, 88, 12, 0.05)' : 'var(--bg-secondary)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>{name}</strong>
                      {phone && <span style={{ fontSize: '11px', color: '#16a34a', fontWeight: '600' }}>WhatsApp Ready</span>}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', gap: '12px' }}>
                      {phone && <span>📞 {phone}</span>}
                      {email && <span>✉️ {email}</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right: Pitch Flyout */}
          <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '18px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: '700', margin: '0 0 12px 0' }}>
              {selectedLead ? `Personalized Offer Pitch for ${selectedLead.company_name || selectedLead['Company Name']}` : 'Personalized Pitch Preview'}
            </h3>

            {generatingPitch && <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>Generating custom pitch...</div>}

            {!generatingPitch && pitchData && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {/* WhatsApp Pitch */}
                <div style={{ background: 'rgba(37, 211, 102, 0.05)', border: '1px solid rgba(37, 211, 102, 0.3)', borderRadius: '10px', padding: '14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontWeight: '700', color: '#128c7e', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Phone size={14} /> WhatsApp Direct Message (Gujarati / English)
                    </span>
                    <button
                      onClick={() => copyToClipboard(pitchData.whatsapp_pitch_gu, 'WhatsApp Pitch')}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#128c7e', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}
                    >
                      <Copy size={13} /> Copy
                    </button>
                  </div>
                  <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: '12.5px', color: 'var(--text-primary)', margin: 0, lineHeight: '1.5' }}>
                    {pitchData.whatsapp_pitch_gu}
                  </pre>
                  {pitchData.whatsapp_url && (
                    <a
                      href={pitchData.whatsapp_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        background: '#25D366',
                        color: '#fff',
                        textDecoration: 'none',
                        padding: '8px 14px',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: '700',
                        marginTop: '12px'
                      }}
                    >
                      <Share2 size={14} /> Send via WhatsApp Web / App
                    </a>
                  )}
                </div>

                {/* Email Pitch */}
                <div style={{ background: 'rgba(59, 130, 246, 0.05)', border: '1px solid rgba(59, 130, 246, 0.3)', borderRadius: '10px', padding: '14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontWeight: '700', color: '#2563eb', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Mail size={14} /> Email Outreach Pitch
                    </span>
                    <button
                      onClick={() => copyToClipboard(pitchData.email_body, 'Email Pitch')}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#2563eb', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}
                    >
                      <Copy size={13} /> Copy
                    </button>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '6px' }}>
                    <strong>Subject:</strong> {pitchData.email_subject}
                  </div>
                  <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: '12px', color: 'var(--text-primary)', margin: 0, lineHeight: '1.5' }}>
                    {pitchData.email_body}
                  </pre>
                  {pitchData.mailto_url && (
                    <a
                      href={pitchData.mailto_url}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        background: '#2563eb',
                        color: '#fff',
                        textDecoration: 'none',
                        padding: '8px 14px',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: '700',
                        marginTop: '12px'
                      }}
                    >
                      <ExternalLink size={14} /> Open in Email App
                    </a>
                  )}
                </div>

                {/* WhatsApp Multi-Touch Follow-Up Cadence */}
                {pitchData.followups && (
                  <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                      <Phone size={14} color="#16a34a" />
                      <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                        Multi-Touch WhatsApp Cadence (Unresponsive Leads)
                      </strong>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {/* Day 1 */}
                      <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '10px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontSize: '11px', fontWeight: '800', color: '#2563eb' }}>DAY 1: 24h NUDGE</span>
                          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            <button
                              onClick={() => copyToClipboard(pitchData.followups.day1.gu, 'Day 1 Follow-up')}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '11px', color: 'var(--text-muted)' }}
                            >
                              Copy
                            </button>
                            {pitchData.followups.day1.wa_url_gu && (
                              <a
                                href={pitchData.followups.day1.wa_url_gu}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ background: '#25D366', color: '#fff', textDecoration: 'none', padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '700' }}
                              >
                                Send WhatsApp
                              </a>
                            )}
                          </div>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{pitchData.followups.day1.gu}</div>
                      </div>

                      {/* Day 3 */}
                      <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '10px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontSize: '11px', fontWeight: '800', color: '#ea580c' }}>DAY 3: SAMPLE SHOWCASE</span>
                          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            <button
                              onClick={() => copyToClipboard(pitchData.followups.day3.gu, 'Day 3 Follow-up')}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '11px', color: 'var(--text-muted)' }}
                            >
                              Copy
                            </button>
                            {pitchData.followups.day3.wa_url_gu && (
                              <a
                                href={pitchData.followups.day3.wa_url_gu}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ background: '#25D366', color: '#fff', textDecoration: 'none', padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '700' }}
                              >
                                Send WhatsApp
                              </a>
                            )}
                          </div>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{pitchData.followups.day3.gu}</div>
                      </div>

                      {/* Day 6 */}
                      <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '10px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontSize: '11px', fontWeight: '800', color: '#64748b' }}>DAY 6: POLITE CLOSE</span>
                          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            <button
                              onClick={() => copyToClipboard(pitchData.followups.day6.gu, 'Day 6 Follow-up')}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '11px', color: 'var(--text-muted)' }}
                            >
                              Copy
                            </button>
                            {pitchData.followups.day6.wa_url_gu && (
                              <a
                                href={pitchData.followups.day6.wa_url_gu}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ background: '#25D366', color: '#fff', textDecoration: 'none', padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '700' }}
                              >
                                Send WhatsApp
                              </a>
                            )}
                          </div>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{pitchData.followups.day6.gu}</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {!generatingPitch && !pitchData && (
              <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                👈 Click on any lead from the left to generate its instant ₹500 Festival Pitch!
              </div>
            )}
          </div>
        </div>
      )}

      {/* ======================= TAB 2: ENROLLED CLIENTS ======================= */}
      {activeSubTab === 'clients' && (
        <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: '700', margin: 0 }}>
              Paying Clients ({clients.length})
            </h3>
            <button
              onClick={() => setShowClientModal(true)}
              style={{
                background: '#ea580c',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                padding: '8px 14px',
                fontSize: '12px',
                fontWeight: '600',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <Plus size={14} /> Add Client
            </button>
          </div>

          {clients.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No clients enrolled yet. Click "Enroll Paying Client" to add your first ₹500 or ₹1,000 digital media client!
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '10px 8px' }}>Business Name</th>
                    <th style={{ padding: '10px 8px' }}>Owner / Contact</th>
                    <th style={{ padding: '10px 8px' }}>Pack</th>
                    <th style={{ padding: '10px 8px' }}>Paid (INR)</th>
                    <th style={{ padding: '10px 8px' }}>Status</th>
                    <th style={{ padding: '10px 8px' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {clients.map((c) => (
                    <tr key={c.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '12px 8px' }}>
                        <div style={{ fontWeight: '700', color: 'var(--text-primary)' }}>{c.business_name}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{c.address}</div>
                      </td>
                      <td style={{ padding: '12px 8px' }}>
                        <div>{c.owner_name || '—'}</div>
                        <div style={{ fontSize: '11px', color: '#16a34a' }}>📞 {c.phone}</div>
                      </td>
                      <td style={{ padding: '12px 8px' }}>
                        <span style={{ background: '#ffedd5', color: '#ea580c', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: '700' }}>
                          {c.pack === 'fest_10_pack' ? '10 Festival Posts' : c.pack === 'reels_3_pack' ? '3 Reels' : 'Combo Booster'}
                        </span>
                      </td>
                      <td style={{ padding: '12px 8px', fontWeight: '700', color: '#16a34a' }}>
                        ₹{c.paid_amount || 500}
                      </td>
                      <td style={{ padding: '12px 8px' }}>
                        <span style={{ color: '#10b981', fontWeight: '600', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <CheckCircle2 size={13} /> {c.status}
                        </span>
                      </td>
                      <td style={{ padding: '12px 8px' }}>
                        <button
                          onClick={() => {
                            setStudioClient(c);
                            setActiveSubTab('studio');
                          }}
                          style={{
                            background: 'var(--bg-secondary)',
                            border: '1px solid var(--border-color)',
                            borderRadius: '4px',
                            padding: '4px 8px',
                            fontSize: '11px',
                            cursor: 'pointer'
                          }}
                        >
                          🎨 Open in Studio
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ======================= TAB 3: AI CREATIVE STUDIO & PREVIEW ======================= */}
      {activeSubTab === 'studio' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: '20px' }}>
          {/* Controls */}
          <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '18px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: '700', margin: '0 0 14px 0' }}>🎨 Creative Customizer</h3>

            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                Select Festival
              </label>
              <select
                value={selectedFestival}
                onChange={(e) => setSelectedFestival(e.target.value)}
                style={{ width: '100%', padding: '9px 10px', borderRadius: '8px', border: '1px solid var(--border-color)', fontSize: '13px' }}
              >
                {(offersData?.calendar || []).map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} ({f.gujarati_name})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                Select Paying Client (or type custom)
              </label>
              <select
                onChange={(e) => {
                  const found = clients.find((c) => c.id === e.target.value);
                  if (found) setStudioClient(found);
                }}
                style={{ width: '100%', padding: '9px 10px', borderRadius: '8px', border: '1px solid var(--border-color)', fontSize: '13px' }}
              >
                <option value="">-- Choose Client --</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.business_name} ({c.phone})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Business Name on Banner</label>
                <input
                  type="text"
                  value={studioClient.business_name || ''}
                  onChange={(e) => setStudioClient({ ...studioClient, business_name: e.target.value })}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border-color)', fontSize: '13px', boxSizing: 'border-box' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Tagline / Slogan</label>
                <input
                  type="text"
                  value={studioClient.tagline || ''}
                  onChange={(e) => setStudioClient({ ...studioClient, tagline: e.target.value })}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border-color)', fontSize: '13px', boxSizing: 'border-box' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Phone Number</label>
                <input
                  type="text"
                  value={studioClient.phone || ''}
                  onChange={(e) => setStudioClient({ ...studioClient, phone: e.target.value })}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border-color)', fontSize: '13px', boxSizing: 'border-box' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Address</label>
                <input
                  type="text"
                  value={studioClient.address || ''}
                  onChange={(e) => setStudioClient({ ...studioClient, address: e.target.value })}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border-color)', fontSize: '13px', boxSizing: 'border-box' }}
                />
              </div>
            </div>

            <div style={{ marginTop: '20px', display: 'flex', gap: '10px' }}>
              <button
                onClick={downloadAsPng}
                style={{
                  flex: 1,
                  background: 'linear-gradient(135deg, #10b981, #059669)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '10px 0',
                  fontSize: '13px',
                  fontWeight: '700',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px'
                }}
              >
                <Download size={15} /> Download PNG (1080x1080)
              </button>

              <button
                onClick={() => handleScheduleDispatch(studioClient.id || 'temp', selectedFestival)}
                style={{
                  flex: 1,
                  background: '#ea580c',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '10px 0',
                  fontSize: '13px',
                  fontWeight: '700',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px'
                }}
              >
                <Calendar size={15} /> Schedule Dispatch
              </button>
            </div>
          </div>

          {/* Live SVG Preview */}
          <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '18px', textAlign: 'center' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: '700', margin: 0 }}>HD Publication Preview (1:1 Square)</h3>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>1080 × 1080 px</span>
            </div>

            <div
              style={{
                width: '100%',
                maxWidth: '460px',
                aspectRatio: '1/1',
                margin: '0 auto',
                borderRadius: '12px',
                overflow: 'hidden',
                boxShadow: '0 8px 30px rgba(0,0,0,0.15)',
                background: '#000'
              }}
              dangerouslySetInnerHTML={{ __html: generatedSvg }}
            />
          </div>
        </div>
      )}

      {/* ======================= TAB 4: SCHEDULED DELIVERIES ======================= */}
      {activeSubTab === 'schedules' && (
        <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '20px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '700', margin: '0 0 16px 0' }}>
            Scheduled Automated Festival Dispatches ({schedules.length})
          </h3>

          {schedules.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No dispatches scheduled yet. Go to Creative Studio to schedule posts for upcoming festivals!
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '10px 8px' }}>Client Name</th>
                    <th style={{ padding: '10px 8px' }}>Festival</th>
                    <th style={{ padding: '10px 8px' }}>Dispatch Date</th>
                    <th style={{ padding: '10px 8px' }}>WhatsApp Number</th>
                    <th style={{ padding: '10px 8px' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map((s) => (
                    <tr key={s.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '12px 8px', fontWeight: '600' }}>{s.client_name}</td>
                      <td style={{ padding: '12px 8px' }}>
                        <strong>{s.festival_name}</strong> ({s.gujarati_name})
                      </td>
                      <td style={{ padding: '12px 8px', color: '#ea580c', fontWeight: '600' }}>
                        {s.dispatch_date || 'Festival Day'}
                      </td>
                      <td style={{ padding: '12px 8px' }}>{s.client_phone}</td>
                      <td style={{ padding: '12px 8px' }}>
                        <span
                          style={{
                            background: s.status === 'DISPATCHED' ? '#dcfce7' : '#fef3c7',
                            color: s.status === 'DISPATCHED' ? '#16a34a' : '#d97706',
                            padding: '3px 8px',
                            borderRadius: '10px',
                            fontSize: '11px',
                            fontWeight: '700'
                          }}
                        >
                          {s.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ======================= TAB 5: 20-YEAR BDE STRATEGY PLAYBOOK ======================= */}
      {activeSubTab === 'strategy' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Core Philosophy Banner */}
          <div
            style={{
              background: 'linear-gradient(135deg, #1e293b, #0f172a)',
              color: '#fff',
              borderRadius: '12px',
              padding: '24px',
              border: '1px solid #334155'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <Sparkles size={20} color="#f59e0b" />
              <span style={{ fontSize: '12px', fontWeight: '800', color: '#f59e0b', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                20-Year BDE Master Playbook
              </span>
            </div>
            <h2 style={{ fontSize: '20px', fontWeight: '800', margin: '0 0 10px 0' }}>
              The Trojan Horse / Tripwire Acquisition Funnel
            </h2>
            <p style={{ margin: 0, fontSize: '13.5px', color: '#cbd5e1', lineHeight: '1.7', maxWidth: '900px' }}>
              <strong>The Secret:</strong> The ₹500 pack is <em>not</em> meant for direct margin profit. It is a zero-friction &quot;foot-in-the-door&quot; to convert cold strangers into paying clients with an immediate UPI payment, breaking stranger risk and establishing high trust. Once they pay ₹500, they become an active customer ready for our <strong>₹15,000 - ₹1,00,000 IT project upselling</strong> (Websites, Mobile Apps, CRM, ERP).
            </p>
          </div>

          {/* 3 Target Tiers */}
          <div>
            <h3 style={{ fontSize: '16px', fontWeight: '700', marginBottom: '12px', color: 'var(--text-primary)' }}>
              🎯 Target Market Tiers (Prioritized by Conversion Speed)
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
              <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '16px' }}>
                <span style={{ background: '#ffedd5', color: '#ea580c', fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '10px' }}>
                  TIER 1 (FASTEST CLOSE)
                </span>
                <h4 style={{ margin: '8px 0 4px 0', fontSize: '15px', fontWeight: '700' }}>Retailers & Local Services</h4>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '10px' }}>
                  Sweets & Farsan, Cafes, Boutiques, Jewellers, Real Estate Brokers, Clinics & Doctors.
                </p>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', background: 'var(--bg-secondary)', padding: '8px 10px', borderRadius: '6px' }}>
                  ⚡ <strong>Speed:</strong> Closes in &lt; 4 hours. Decisions made on the spot via UPI.
                </div>
              </div>

              <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '16px' }}>
                <span style={{ background: '#dbeafe', color: '#2563eb', fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '10px' }}>
                  TIER 2 (GIDC / MSMEs)
                </span>
                <h4 style={{ margin: '8px 0 4px 0', fontSize: '15px', fontWeight: '700' }}>Industrial Manufacturers</h4>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '10px' }}>
                  Packaging, Machinery Tools, Chemicals, Textiles (Vatva, Odhav, Sanand, Changodar).
                </p>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', background: 'var(--bg-secondary)', padding: '8px 10px', borderRadius: '6px' }}>
                  🏭 <strong>Need:</strong> Professional posts for dealer/distributor WhatsApp status.
                </div>
              </div>

              <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '16px' }}>
                <span style={{ background: '#ede9fe', color: '#7c3aed', fontSize: '11px', fontWeight: '800', padding: '3px 8px', borderRadius: '10px' }}>
                  TIER 3 (AUTHORITY)
                </span>
                <h4 style={{ margin: '8px 0 4px 0', fontSize: '15px', fontWeight: '700' }}>Professional Consultancies</h4>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '10px' }}>
                  Chartered Accountants, Lawyers, Architects, Interior Designers, Visa Consultants.
                </p>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', background: 'var(--bg-secondary)', padding: '8px 10px', borderRadius: '6px' }}>
                  📈 <strong>Need:</strong> High-trust educational post designs & compliance updates.
                </div>
              </div>
            </div>
          </div>

          {/* Daily 100 Cadence & Upsell Ladder */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '16px' }}>
            {/* Daily Cadence */}
            <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '18px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: '700', margin: '0 0 14px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Clock size={16} color="#ea580c" /> Daily 100 Lead Cadence (BDE Routine)
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12.5px' }}>
                <div style={{ borderLeft: '3px solid #2563eb', paddingLeft: '10px' }}>
                  <strong>09:30 AM - 11:00 AM: Email Dispatch (50-100/day)</strong>
                  <div style={{ color: 'var(--text-muted)' }}>Send automated short outreach to active master leads.</div>
                </div>
                <div style={{ borderLeft: '3px solid #10b981', paddingLeft: '10px' }}>
                  <strong>11:30 AM - 01:30 PM: WhatsApp Pings (30-50/day)</strong>
                  <div style={{ color: 'var(--text-muted)' }}>Ping WhatsApp active leads with the 2-line Gujarati/English pitch.</div>
                </div>
                <div style={{ borderLeft: '3px solid #f59e0b', paddingLeft: '10px' }}>
                  <strong>02:00 PM - 04:00 PM: The &apos;Instant Sample&apos; Hammer</strong>
                  <div style={{ color: 'var(--text-muted)' }}>When a lead replies &apos;YES&apos;, generate 1 branded sample in 30 mins to close payment.</div>
                </div>
                <div style={{ borderLeft: '3px solid #8b5cf6', paddingLeft: '10px' }}>
                  <strong>04:30 PM - 06:30 PM: Enroll & Delivery Scheduling</strong>
                  <div style={{ color: 'var(--text-muted)' }}>Collect UPI payments (₹500 / ₹1,000) and enroll into automated delivery.</div>
                </div>
              </div>
            </div>

            {/* Upsell Ladder */}
            <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '18px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: '700', margin: '0 0 14px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle2 size={16} color="#10b981" /> The Upselling Ladder (₹500 ➔ ₹50,000)
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12.5px' }}>
                <div style={{ background: 'var(--bg-secondary)', padding: '8px 10px', borderRadius: '6px' }}>
                  <strong>Day 0 (Acquisition):</strong> 10 Images For Posts @ ₹500. Goal: Build payment trust.
                </div>
                <div style={{ background: 'var(--bg-secondary)', padding: '8px 10px', borderRadius: '6px' }}>
                  <strong>Day 3 (Website Audit):</strong> Pitch high-speed mobile website revamps (₹9,999 - ₹18,000).
                </div>
                <div style={{ background: 'var(--bg-secondary)', padding: '8px 10px', borderRadius: '6px' }}>
                  <strong>Day 7-10 (Custom IT):</strong> Pitch WhatsApp Lead CRM & Billing Software (₹25,000 - ₹75,000).
                </div>
                <div style={{ background: 'var(--bg-secondary)', padding: '8px 10px', borderRadius: '6px' }}>
                  <strong>Day 30 (Retention):</strong> Monthly retainer (₹5,000/mo) or ₹450/hr dedicated developer.
                </div>
              </div>
            </div>
          </div>

          {/* Winning Objection Handlers */}
          <div style={{ background: 'var(--bg-card, #fff)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '18px' }}>
            <h3 style={{ fontSize: '15px', fontWeight: '700', margin: '0 0 14px 0' }}>
              💬 Gujarati / Indian SME Objection Handling Matrix
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '12px' }}>
                <div style={{ fontSize: '12px', fontWeight: '700', color: '#ea580c', marginBottom: '4px' }}>
                  &ldquo;Ame potey Canva par banavi laiye chiye (We make it ourselves)&rdquo;
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                  <strong>Rebuttal:</strong> &ldquo;Bilkul barabar sir! But tamaro 1 kalak no time business chalavva mate ₹2,000 thi vadhu kimti che. Fakt ₹50 per post ma tamne agency-level finishing male che vagar koi samay bagadye.&rdquo;
                </div>
              </div>

              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '12px' }}>
                <div style={{ fontSize: '12px', fontWeight: '700', color: '#ea580c', marginBottom: '4px' }}>
                  &ldquo;Pehle sample moklo pachi vichariyu (Send sample first)&rdquo;
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                  <strong>Rebuttal:</strong> &ldquo;Done sir! Tamara business mate 1 customised branded sample tamne 30 minute ma WhatsApp kariye chiye. Pasand aave toh j baki na 9 posts no order aapjo.&rdquo;
                </div>
              </div>

              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '12px' }}>
                <div style={{ fontSize: '12px', fontWeight: '700', color: '#ea580c', marginBottom: '4px' }}>
                  &ldquo;Aamathi mane client / dhandho malse? (Will this bring sales?)&rdquo;
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                  <strong>Rebuttal:</strong> &ldquo;Sir, koi pan customer tamaro contact kare tyare pehla tamaru WhatsApp Status ane Profile jove che. Professional post joi ne customer ma trust 10x vadhi jaay che ane deal jaldi close thaay che.&rdquo;
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ======================= CLIENT ONBOARDING MODAL ======================= */}
      {showClientModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px'
          }}
        >
          <div
            style={{
              background: 'var(--bg-card, #fff)',
              borderRadius: '16px',
              maxWidth: '520px',
              width: '100%',
              padding: '24px',
              boxShadow: '0 20px 40px rgba(0,0,0,0.3)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '18px', fontWeight: '700', margin: 0 }}>Enroll Paying Client</h3>
              <button onClick={() => setShowClientModal(false)} style={{ background: 'none', border: 'none', fontSize: '18px', cursor: 'pointer' }}>
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveClient} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: '600' }}>Business Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Radhe Krishna Sweets"
                  value={clientForm.business_name}
                  onChange={(e) => setClientForm({ ...clientForm, business_name: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-color)', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: '600' }}>Owner Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Ramesh Patel"
                    value={clientForm.owner_name}
                    onChange={(e) => setClientForm({ ...clientForm, owner_name: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-color)', boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: '600' }}>WhatsApp Phone *</label>
                  <input
                    type="text"
                    required
                    placeholder="+91 98980XXXXX"
                    value={clientForm.phone}
                    onChange={(e) => setClientForm({ ...clientForm, phone: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-color)', boxSizing: 'border-box' }}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: '600' }}>Tagline / Business Nature</label>
                <input
                  type="text"
                  placeholder="e.g. Pure Desi Ghee Sweets & Farsan"
                  value={clientForm.tagline}
                  onChange={(e) => setClientForm({ ...clientForm, tagline: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-color)', boxSizing: 'border-box' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: '600' }}>Address to Print on Creative</label>
                <input
                  type="text"
                  placeholder="e.g. Ashram Road, Ahmedabad"
                  value={clientForm.address}
                  onChange={(e) => setClientForm({ ...clientForm, address: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-color)', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: '600' }}>Package</label>
                  <select
                    value={clientForm.pack}
                    onChange={(e) => {
                      const val = e.target.value;
                      const price = val === 'fest_10_pack' ? 500 : val === 'reels_3_pack' ? 1000 : 1299;
                      setClientForm({ ...clientForm, pack: val, paid_amount: price });
                    }}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-color)', boxSizing: 'border-box' }}
                  >
                    <option value="fest_10_pack">10 Festival Posts (₹500)</option>
                    <option value="reels_3_pack">3 Video Reels (₹1,000)</option>
                    <option value="combo_festive_booster">Combo Booster (₹1,299)</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: '600' }}>Payment Collected</label>
                  <input
                    type="number"
                    value={clientForm.paid_amount}
                    onChange={(e) => setClientForm({ ...clientForm, paid_amount: Number(e.target.value) })}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-color)', boxSizing: 'border-box' }}
                  />
                </div>
              </div>

              <div style={{ marginTop: '14px', display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => setShowClientModal(false)}
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{ background: '#ea580c', color: '#fff', border: 'none', padding: '8px 18px', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}
                >
                  Save & Enroll
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

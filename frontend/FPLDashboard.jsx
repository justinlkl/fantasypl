'use client'

import { useState, useMemo, useCallback } from "react"
import {
  BarChart, Bar, LineChart, Line, ComposedChart,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from "recharts"
import {
  Search, X, Check, ChevronDown, ChevronUp,
  RefreshCw, Users, Shield, Activity, Star,
  Zap, BarChart2, Settings, ArrowLeft, Sliders
} from "lucide-react"
import { usePredictions, useFixtureTicker, useTeams, useLiveMatches, useLivePoints, useFixtures } from "./lib/hooks"

/* ── TOKENS ─────────────────────────────────────────────────── */
const BG="#07101f",CARD="#0c1828",C2="#101f35",C3="#152440"
const BD="#1a2d46",BD2="#223659"
const TX="#c8d6ed",MU="#4a6080",MU2="#688099"
const ACT="#3b82f6",GR="#10b981",RD="#ef4444"
const AM="#f59e0b",IN="#6366f1",PRP="#a855f7"
const POS_C={GK:"#f59e0b",DEF:"#60a5fa",MID:"#34d399",FWD:"#f87171"}
const FDR_B={1:"#00ff87",2:"#01d966",3:"#1a2d46",4:"#e8143e",5:"#7a063c"}
const FDR_T={1:"#003319",2:"#002210",3:"#5a7599",4:"#fff",5:"#ffccdd"}

/* ── STYLE HELPERS ──────────────────────────────────────────── */
const cs =(x={})=>({background:CARD,border:`1px solid ${BD}`,borderRadius:8,...x})
const c2s=(x={})=>({background:C2,  border:`1px solid ${BD}`,borderRadius:8,...x})
const TH={background:C2,padding:"7px 9px",fontSize:9.5,color:MU,textTransform:"uppercase",letterSpacing:"0.08em",textAlign:"left",borderBottom:`1px solid ${BD}`,whiteSpace:"nowrap",fontWeight:700,userSelect:"none"}
const TD={padding:"8px 9px",fontSize:12,borderBottom:`1px solid ${BD}1a`,whiteSpace:"nowrap",color:TX}
const mn={fontFamily:"'DM Mono',monospace"}
const ptag=pos=>({background:POS_C[pos]+"22",color:POS_C[pos],padding:"2px 5px",borderRadius:3,fontSize:9,fontWeight:700,display:"inline-block",minWidth:28,textAlign:"center"})
const fdp=f=>({background:FDR_B[f]||FDR_B[3],color:FDR_T[f]||FDR_T[3],padding:"2px 5px",borderRadius:3,fontSize:9,fontWeight:700,textAlign:"center",display:"inline-block"})
const n2=v=>typeof v==="number"?v.toFixed(2):"—"
const n1=v=>typeof v==="number"?v.toFixed(1):"—"
const ni=v=>typeof v==="number"?String(Math.round(v)):"—"
const toNum=(v,f=0)=>{
  const n=typeof v==="number"?v:Number(v)
  return Number.isFinite(n)?n:f
}
const pickNum=(obj,keys,f=0)=>{
  for(const k of keys){
    const v=obj?.[k]
    if(v!=null&&v!==""&&Number.isFinite(Number(v)))return Number(v)
  }
  return f
}
const clamp=(n,min,max)=>Math.min(max,Math.max(min,n))
const chancePct=v=>v==null?100:(v<=1?Number(v)*100:Number(v))

function Btn({onClick,children,variant="ghost",small=false,active=false,style:sx={},disabled=false}){
  const base={display:"inline-flex",alignItems:"center",gap:4,cursor:disabled?"default":"pointer",border:"none",borderRadius:5,fontWeight:600,fontFamily:"inherit",opacity:disabled?0.4:1,lineHeight:1}
  const p=small?"3px 8px":"6px 12px",fs=small?10:12
  const V={
    ghost:{...base,background:active?C3:"transparent",color:active?TX:MU,border:`1px solid ${active?BD2:BD}`,padding:p,fontSize:fs},
    primary:{...base,background:ACT+"22",color:ACT,border:`1px solid ${ACT}44`,padding:p,fontSize:fs},
    green:{...base,background:GR+"1a",color:GR,border:`1px solid ${GR}44`,padding:p,fontSize:fs},
    danger:{...base,background:RD+"18",color:RD,border:`1px solid ${RD}44`,padding:p,fontSize:fs},
    amber:{...base,background:AM+"1a",color:AM,border:`1px solid ${AM}44`,padding:p,fontSize:fs},
    tab:{...base,background:active?ACT+"1a":"transparent",color:active?ACT:MU,border:"none",borderBottom:`2px solid ${active?ACT:"transparent"}`,padding:"12px 14px",borderRadius:0,fontSize:12.5},
  }
  return <button onClick={onClick} disabled={disabled} style={{...V[variant],...sx}}>{children}</button>
}

function Tag({label,color}){return<span style={{background:color+"1a",color,padding:"1px 5px",borderRadius:3,fontSize:9,fontWeight:700}}>{label}</span>}

function SortTH({col,label,sort,setSort,right=false}){
  const a=sort.col===col
  return(
    <th style={{...TH,cursor:"pointer",textAlign:right?"right":"left"}} onClick={()=>setSort(s=>({col,dir:s.col===col?-s.dir:-1}))}>
      <span style={{display:"flex",alignItems:"center",gap:2,justifyContent:right?"flex-end":"flex-start",color:a?TX:MU}}>
        {label}{a?(sort.dir===-1?<ChevronDown size={8}/>:<ChevronUp size={8}/>):<ChevronDown size={8} style={{opacity:.18}}/>}
      </span>
    </th>
  )
}

const FDRStrip=({fdrs=[],size=9})=>(
  <div style={{display:"flex",gap:2}}>{fdrs.map((f,i)=><div key={i} style={{width:size,height:4,borderRadius:1,background:FDR_B[f]||FDR_B[3]}}/>)}</div>
)

const Spark=({data=[],color=GR,w=56,h=18})=>{
  if(!data.length)return null
  const mx=Math.max(...data,1)
  return<svg width={w} height={h} style={{display:"block"}}><polyline points={data.map((v,i)=>`${(i/(data.length-1))*w},${h-(v/mx)*h}`).join(" ")} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round"/></svg>
}

const CT=({active,payload,label})=>{
  if(!active||!payload?.length)return null
  return<div style={{background:C2,border:`1px solid ${BD2}`,borderRadius:6,padding:"8px 12px",fontSize:12}}>
    <div style={{color:MU,marginBottom:4}}>{label}</div>
    {payload.map((p,i)=><div key={i} style={{color:p.color||TX}}>{p.name}: <b style={mn}>{typeof p.value==="number"?p.value.toFixed(2):p.value}</b></div>)}
  </div>
}

const SliderRow=({label,val,setVal,min=0,max=100,step=5,color=ACT,desc=""})=>(
  <div style={{marginBottom:12}}>
    <div style={{display:"flex",justifyContent:"space-between",marginBottom:3}}>
      <div><div style={{fontSize:12,fontWeight:600,color:TX}}>{label}</div>{desc&&<div style={{fontSize:10,color:MU}}>{desc}</div>}</div>
      <span style={{fontSize:12,fontWeight:700,color,...mn}}>{val}{max===100?"%":""}</span>
    </div>
    <div style={{position:"relative",height:6,background:BD,borderRadius:3}}>
      <div style={{position:"absolute",left:0,top:0,height:"100%",width:`${(val-min)/(max-min)*100}%`,background:color,borderRadius:3}}/>
      <input type="range" min={min} max={max} step={step} value={val} onChange={e=>setVal(+e.target.value)} style={{position:"absolute",inset:0,width:"100%",opacity:0,cursor:"pointer",height:"100%"}}/>
    </div>
  </div>
)

/* ── GENERATORS ─────────────────────────────────────────────── */
const rng=seed=>{let s=seed>>>0;return()=>{s=Math.imul(s^s>>>15,s|1);s^=s+Math.imul(s^s>>>7,s|61);return((s^s>>>14)>>>0)/4294967296}}
const gp=(form,seed)=>{const r=rng(seed);return Array.from({length:15},()=>Math.max(0,Math.round(form+(r()-0.5)*form*1.6)))}

/* ── FIXTURE DATA ───────────────────────────────────────────── */
const TF={
  LIV:[{o:"BOU",h:1,f:2,af:1,df:2},{o:"NOT",h:0,f:2,af:2,df:2},{o:"WHU",h:1,f:1,af:1,df:2},{o:"ARS",h:0,f:3,af:3,df:3},{o:"AVL",h:1,f:2,af:2,df:2}],
  MCI:[{o:"BRI",h:0,f:1,af:1,df:2},{o:"TOT",h:1,f:3,af:2,df:3},{o:"MUN",h:0,f:2,af:2,df:3},{o:"CHE",h:1,f:3,af:2,df:3},{o:"NOT",h:0,f:2,af:2,df:2}],
  CHE:[{o:"EVE",h:1,f:1,af:1,df:2},{o:"BRE",h:0,f:2,af:2,df:2},{o:"ARS",h:1,f:3,af:3,df:3},{o:"MCI",h:0,f:5,af:5,df:4},{o:"AVL",h:1,f:2,af:2,df:2}],
  ARS:[{o:"WOL",h:1,f:1,af:1,df:2},{o:"FUL",h:0,f:2,af:2,df:2},{o:"CHE",h:0,f:3,af:3,df:2},{o:"NOT",h:1,f:2,af:2,df:2},{o:"LIV",h:1,f:3,af:3,df:3}],
  TOT:[{o:"WHU",h:1,f:2,af:1,df:2},{o:"MCI",h:0,f:4,af:4,df:3},{o:"BRI",h:1,f:2,af:2,df:2},{o:"BOU",h:0,f:1,af:1,df:2},{o:"LEE",h:1,f:1,af:1,df:1}],
  AVL:[{o:"CRY",h:1,f:1,af:1,df:1},{o:"SUN",h:0,f:1,af:1,df:2},{o:"BOU",h:1,f:1,af:1,df:1},{o:"FUL",h:0,f:2,af:2,df:2},{o:"LIV",h:0,f:4,af:4,df:3}],
  NEW:[{o:"BUR",h:1,f:1,af:1,df:2},{o:"FUL",h:0,f:2,af:2,df:2},{o:"WOL",h:1,f:1,af:1,df:1},{o:"LIV",h:0,f:4,af:4,df:3},{o:"BRE",h:0,f:2,af:2,df:2}],
  MUN:[{o:"LEE",h:1,f:1,af:1,df:1},{o:"NOT",h:0,f:2,af:2,df:2},{o:"MCI",h:1,f:4,af:4,df:3},{o:"AVL",h:1,f:2,af:2,df:2},{o:"BRI",h:0,f:2,af:2,df:2}],
  WHU:[{o:"TOT",h:0,f:3,af:2,df:3},{o:"CRY",h:1,f:1,af:1,df:1},{o:"LIV",h:0,f:4,af:4,df:3},{o:"BRE",h:1,f:2,af:2,df:2},{o:"FUL",h:0,f:2,af:2,df:2}],
  BRE:[{o:"SUN",h:1,f:1,af:1,df:1},{o:"CHE",h:1,f:3,af:2,df:3},{o:"FUL",h:0,f:2,af:2,df:2},{o:"WHU",h:0,f:2,af:2,df:2},{o:"NEW",h:1,f:3,af:2,df:3}],
  BRI:[{o:"MCI",h:1,f:5,af:4,df:5},{o:"WOL",h:0,f:1,af:1,df:1},{o:"TOT",h:0,f:3,af:2,df:3},{o:"BUR",h:1,f:1,af:1,df:1},{o:"MUN",h:1,f:2,af:2,df:2}],
  EVE:[{o:"CHE",h:0,f:3,af:2,df:3},{o:"BUR",h:1,f:1,af:1,df:1},{o:"WOL",h:0,f:1,af:1,df:1},{o:"CRY",h:1,f:1,af:1,df:1},{o:"ARS",h:1,f:4,af:4,df:3}],
  NOT:[{o:"AVL",h:0,f:3,af:2,df:3},{o:"MUN",h:1,f:2,af:2,df:2},{o:"LEE",h:0,f:1,af:1,df:1},{o:"ARS",h:0,f:4,af:4,df:3},{o:"MCI",h:1,f:4,af:4,df:3}],
  FUL:[{o:"BUR",h:1,f:1,af:1,df:1},{o:"ARS",h:1,f:4,af:3,df:4},{o:"BRE",h:1,f:2,af:2,df:2},{o:"AVL",h:1,f:2,af:2,df:2},{o:"WHU",h:1,f:2,af:2,df:2}],
  CRY:[{o:"AVL",h:0,f:2,af:2,df:2},{o:"WHU",h:0,f:2,af:2,df:2},{o:"SUN",h:1,f:1,af:1,df:1},{o:"EVE",h:0,f:1,af:1,df:1},{o:"BUR",h:1,f:1,af:1,df:1}],
  BOU:[{o:"LIV",h:0,f:4,af:4,df:3},{o:"CRY",h:1,f:1,af:1,df:1},{o:"AVL",h:0,f:2,af:2,df:2},{o:"TOT",h:1,f:3,af:2,df:3},{o:"BUR",h:0,f:1,af:1,df:1}],
  WOL:[{o:"ARS",h:0,f:4,af:3,df:4},{o:"BRI",h:1,f:2,af:1,df:2},{o:"EVE",h:1,f:1,af:1,df:1},{o:"NEW",h:0,f:3,af:2,df:3},{o:"LEE",h:1,f:1,af:1,df:1}],
  BUR:[{o:"FUL",h:0,f:2,af:2,df:2},{o:"AVL",h:1,f:2,af:1,df:2},{o:"EVE",h:0,f:1,af:1,df:1},{o:"BRI",h:0,f:2,af:2,df:2},{o:"BOU",h:1,f:1,af:1,df:1}],
  LEE:[{o:"MUN",h:0,f:3,af:2,df:3},{o:"WOL",h:1,f:1,af:1,df:1},{o:"NOT",h:1,f:2,af:2,df:2},{o:"SUN",h:0,f:1,af:1,df:1},{o:"TOT",h:0,f:4,af:3,df:4}],
  SUN:[{o:"BRE",h:0,f:2,af:2,df:2},{o:"AVL",h:1,f:2,af:1,df:2},{o:"CRY",h:0,f:1,af:1,df:1},{o:"LEE",h:1,f:1,af:1,df:1},{o:"BOU",h:0,f:1,af:1,df:1}],
}
const GW_NEXT=["GW32","GW33","GW34","GW35","GW36"]
const GW_LBLS=Array.from({length:15},(_,i)=>`GW${17+i}`)
const TEAMS_ALL=Object.keys(TF)

/* ── PLAYER DATA ────────────────────────────────────────────── */
const PLmap={}
const PLAYERS=(()=>{
  const RAW=[
    [1,"Salah","LIV","MID",13.5,45.2,8.5,0.82,0.45,0.37,8.2,40.3,0.93,100],
    [2,"Haaland","MCI","FWD",14.2,38.1,7.8,0.95,0.92,0.03,7.5,37.1,0.89,100],
    [3,"Palmer","CHE","MID",11.8,31.4,7.2,0.71,0.38,0.33,6.8,33.5,0.91,100],
    [4,"Saka","ARS","MID",10.5,28.3,7.5,0.68,0.35,0.33,7.1,34.8,0.95,100],
    [5,"Son","TOT","MID",10.2,22.1,6.8,0.58,0.30,0.28,6.5,31.2,0.88,100],
    [6,"Watkins","AVL","FWD",9.2,18.5,7.1,0.72,0.55,0.17,6.9,33.1,0.90,100],
    [7,"Isak","NEW","FWD",9.0,16.8,7.4,0.68,0.52,0.16,7.0,34.2,0.87,100],
    [8,"Mbeumo","BRE","MID",8.5,14.2,7.8,0.65,0.35,0.30,7.4,35.1,0.92,100],
    [9,"Fernandes","MUN","MID",8.8,12.1,6.5,0.55,0.28,0.27,6.2,29.8,0.85,100],
    [10,"Jota","LIV","MID",8.2,11.5,7.0,0.60,0.32,0.28,6.6,31.8,0.82,100],
    [11,"Bowen","WHU","MID",7.8,9.8,6.2,0.52,0.27,0.25,5.8,27.5,0.88,100],
    [12,"Gordon","NEW","MID",8.0,11.8,6.5,0.55,0.28,0.27,6.2,29.4,0.84,100],
    [13,"Wissa","BRE","FWD",7.5,10.2,6.8,0.58,0.45,0.13,6.4,30.5,0.86,100],
    [14,"Kudus","WHU","MID",7.2,8.5,5.8,0.48,0.25,0.23,5.5,25.8,0.80,75],
    [15,"Undav","BRI","FWD",7.0,8.0,6.0,0.52,0.40,0.12,5.7,27.2,0.82,100],
    [16,"TAA","LIV","DEF",7.8,22.5,7.0,0.42,0.18,0.24,6.5,31.0,0.90,100],
    [17,"Trippier","NEW","DEF",7.2,18.4,6.2,0.35,0.15,0.20,5.8,27.5,0.85,100],
    [18,"Gabriel","ARS","DEF",6.3,15.2,5.8,0.18,0.08,0.10,5.5,26.2,0.92,100],
    [19,"Saliba","ARS","DEF",6.2,14.8,5.6,0.16,0.07,0.09,5.3,25.5,0.94,100],
    [20,"Porro","TOT","DEF",6.2,12.4,5.4,0.32,0.12,0.20,5.1,24.8,0.88,100],
    [21,"Cash","AVL","DEF",5.8,9.5,5.2,0.28,0.10,0.18,4.9,23.5,0.85,100],
    [22,"Robertson","LIV","DEF",6.3,11.2,5.8,0.22,0.09,0.13,5.4,26.0,0.87,100],
    [23,"Timber","ARS","DEF",5.5,8.2,5.0,0.20,0.08,0.12,4.7,22.5,0.80,100],
    [24,"McNeil","EVE","MID",5.4,4.2,4.8,0.35,0.18,0.17,4.5,21.5,0.82,100],
    [25,"Pedro","BRI","FWD",6.5,7.2,5.2,0.42,0.32,0.10,4.9,23.8,0.78,100],
    [26,"Raya","ARS","GK",5.6,24.8,6.5,0,0,0,6.0,28.5,0.95,100],
    [27,"Flekken","BRE","GK",5.0,10.2,5.8,0,0,0,5.4,25.8,0.92,100],
    [28,"Pickford","EVE","GK",4.7,8.5,5.2,0,0,0,4.8,23.0,0.90,100],
    [29,"Henderson","NOT","GK",4.5,6.8,4.8,0,0,0,4.5,21.5,0.88,100],
    [30,"Mykolenko","EVE","DEF",4.4,3.8,4.5,0.15,0.06,0.09,4.2,20.1,0.82,100],
  ]
  return RAW.map(([id,name,team,pos,price,own,form,xgi90,xg90,xa90,nextGW,pts5GW,minRel,chance])=>{
    const tf=TF[team]||[]
    const r1=rng(id*13),r2=rng(id*29),r3=rng(id*37),r4=rng(id*53),r5=rng(id*71)
    const mins=Math.round(minRel*90*0.95+r1()*12)
    const m90=mins/90||1
    const goals=pos==="GK"?0:Math.round(xg90*m90*0.9+r2()*0.5)
    const assists=pos==="GK"?0:Math.round(xa90*m90*0.9+r3()*0.5)
    const xg=+(xg90*m90+r4()*0.08).toFixed(2)
    const xa=+(xa90*m90+r5()*0.06).toFixed(2)
    const xgi=+(xg+xa).toFixed(2)
    const gi=goals+assists
    const cs=["GK","DEF"].includes(pos)?Math.round(minRel*0.45+r1()*0.3):0
    const gc=["GK","DEF"].includes(pos)?Math.round((1-minRel)*3+r2()*2):0
    const xgc=["GK","DEF"].includes(pos)?+(gc*1.05+r3()*0.2).toFixed(2):0
    const dc=pos==="GK"?+(form*0.3+r4()*0.5).toFixed(2):pos==="DEF"?+(form*0.7+r4()*1.2).toFixed(2):pos==="MID"?+(form*0.25+r4()*0.7).toFixed(2):+(form*0.08+r4()*0.3).toFixed(2)
    const dcP90=+(dc/m90).toFixed(2)
    const dch=Math.round(dc*0.4+r5()*0.5)
    const tackles=pos==="GK"?+(r1()*0.4).toFixed(2):pos==="DEF"?+(form*0.4+r1()*0.8).toFixed(2):+(form*0.2+r1()*0.5).toFixed(2)
    const cbi=pos==="GK"?+(r2()*0.5).toFixed(2):pos==="DEF"?+(form*0.6+r2()*1.0).toFixed(2):+(form*0.15+r2()*0.4).toFixed(2)
    const rec=+(form*0.3+r3()*0.8).toFixed(2)
    const infl=+(form*8*0.38+r4()*18).toFixed(1)
    const cre=pos==="GK"?+(r5()*8).toFixed(1):+(form*8*0.30+r5()*20).toFixed(1)
    const thr=pos==="GK"?+(r1()*5).toFixed(1):pos==="DEF"?+(form*8*0.15+r1()*12).toFixed(1):+(form*8*0.45+r1()*30).toFixed(1)
    const ict=+(infl+cre+thr).toFixed(1)
    const bps=Math.round(form*6+r2()*18)
    const bonusProb=+(form*0.06+r3()*0.12).toFixed(2)
    const csRate=+(cs/(minRel*0.9+0.1)).toFixed(2)
    const og=r4()<0.04?1:0
    const ps=pos==="GK"&&r5()<0.12?1:0
    const pm=pos!=="GK"&&r1()<0.06?1:0
    const history=gp(form,id*17)
    const points=history.reduce((s,v)=>s+v,0)
    const pts90=+(pts5GW/Math.max(minRel*5,0.5)).toFixed(2)
    const xgc90=["GK","DEF"].includes(pos)?+(xgc/m90).toFixed(2):0
    const p={
      id,name,team,pos,price,own,form,xgi90,xg90,xa90,nextGW,pts5GW,minRel,chance,
      mins,goals,assists,gi,xg,xa,xgi,cs,gc,xgc,dc,dcP90,dch,tackles,cbi,rec,
      infl,cre,thr,ict,bps,bonusProb,csRate,og,ps,pm,points,pts90,xgc90,
      gi90:+(gi/m90).toFixed(2),goals90:+(goals/m90).toFixed(2),assists90:+(assists/m90).toFixed(2),
      fdrs:tf.map(f=>f.f),afdr:tf.map(f=>f.af||f.f),dfdr:tf.map(f=>f.df||f.f),
      opps:tf.map(f=>`${f.o}${f.h?" (H)":" (A)"}`),
      gwPreds:tf.map(f=>+(nextGW*(1+(3-f.f)*0.08)).toFixed(1)),
      history,roll5:history.map((_,i,a)=>i<4?null:+(a.slice(i-4,i+1).reduce((s,v)=>s+v,0)/5).toFixed(1)),
      sellPrice:+(price-0.1).toFixed(1),valueScore:+(pts5GW/price).toFixed(2),isAvail:chance>=75,
    }
    PLmap[id]=p;return p
  })
})()

/* ── STAT COLUMN DEFINITIONS ────────────────────────────────── */
const ALL_COLS=[
  {id:"nextGW",   label:"Points (Next GW)", grp:"predict",  fmt:n1,  color:v=>GR,          bold:true},
  {id:"pts5GW",   label:"Points (Next 5)",  grp:"predict",  fmt:n1,  color:v=>GR,          bold:true},
  {id:"points",   label:"Points",           grp:"predict",  fmt:ni,  color:v=>v>=50?GR:TX},
  {id:"price",    label:"Price",        grp:"info",     fmt:v=>`£${n1(v)}`,color:v=>AM},
  {id:"own",      label:"Ownership",    grp:"info",     fmt:v=>`${n1(v)}%`,color:v=>MU2},
  {id:"mins",     label:"Minutes",      grp:"info",     fmt:ni,  color:v=>v>=60?GR:TX},
  {id:"pts90",    label:"Points per 90",grp:"info",     fmt:n2,  color:v=>v>=6?GR:TX},
  {id:"goals",    label:"Goals",        grp:"attack",   fmt:ni,  color:v=>v>0?GR:TX},
  {id:"goals90",  label:"Goals per 90", grp:"attack",   fmt:n2,  color:v=>TX},
  {id:"xg",       label:"Expected Goals (xG)", grp:"attack",   fmt:n2,  color:v=>TX},
  {id:"xg90",     label:"Expected Goals per 90 (xG/90)", grp:"attack",   fmt:n2,  color:v=>TX},
  {id:"assists",  label:"Assists",      grp:"attack",   fmt:ni,  color:v=>v>0?GR:TX},
  {id:"assists90",label:"Assists per 90",grp:"attack",   fmt:n2,  color:v=>TX},
  {id:"xa",       label:"Expected Assists (xA)", grp:"attack",   fmt:n2,  color:v=>TX},
  {id:"xa90",     label:"Expected Assists per 90 (xA/90)", grp:"attack",   fmt:n2,  color:v=>TX},
  {id:"gi",       label:"Goal Involvements (GI)", grp:"attack",   fmt:ni,  color:v=>v>0?GR:TX},
  {id:"gi90",     label:"Goal Involvements Per 90 (GI/90)", grp:"attack",   fmt:n2,  color:v=>TX},
  {id:"xgi",      label:"Expected Goal Involvements (xGI)", grp:"attack",   fmt:n2,  color:v=>TX},
  {id:"xgi90",    label:"Expected Goal Involvements Per 90 (xGI/90)", grp:"attack",   fmt:n2,  color:v=>v>=0.6?GR:TX, bold:false},
  {id:"cs",       label:"CS",           grp:"defence",  fmt:ni,  color:v=>v>0?GR:TX},
  {id:"gc",       label:"GC",           grp:"defence",  fmt:ni,  color:v=>v>3?RD:TX},
  {id:"xgc",      label:"Expected Goals Conceded (xGC)", grp:"defence",  fmt:n2,  color:v=>TX},
  {id:"xgc90",    label:"xGC per 90",   grp:"defence",  fmt:n2,  color:v=>v<=1.2?GR:TX},
  {id:"dc",       label:"Defensive Contribution (DC)", grp:"defence",  fmt:n2,  color:v=>TX},
  {id:"dcP90",    label:"Defensive Contribution per 90", grp:"defence",  fmt:n2,  color:v=>v>=3?GR:TX},
  {id:"dch",      label:"DC Hits",      grp:"defence",  fmt:ni,  color:v=>TX},
  {id:"tackles",  label:"Tackles",      grp:"defence",  fmt:n2,  color:v=>TX},
  {id:"cbi",      label:"Clearances, Blocks & Interceptions (CBI)", grp:"defence",  fmt:n2,  color:v=>TX},
  {id:"rec",      label:"Recoveries",   grp:"defence",  fmt:n2,  color:v=>TX},
  {id:"ict",      label:"ICT Index",    grp:"ict",      fmt:n1,  color:v=>v>=50?GR:TX},
  {id:"infl",     label:"Influence",    grp:"ict",      fmt:n1,  color:v=>TX},
  {id:"cre",      label:"Creativity",   grp:"ict",      fmt:n1,  color:v=>TX},
  {id:"thr",      label:"Threat",       grp:"ict",      fmt:n1,  color:v=>TX},
  {id:"og",       label:"OG",           grp:"misc",     fmt:ni,  color:v=>v>0?RD:TX},
  {id:"ps",       label:"PS",           grp:"misc",     fmt:ni,  color:v=>v>0?GR:TX},
  {id:"pm",       label:"PM",           grp:"misc",     fmt:ni,  color:v=>v>0?RD:TX},
]
const GRPS=[{id:"predict",l:"Predictions"},{id:"info",l:"Info"},{id:"attack",l:"Attacking"},{id:"defence",l:"Defensive"},{id:"ict",l:"ICT"},{id:"misc",l:"Misc"}]
const DEFAULT_VIS=new Set(["nextGW","pts5GW","points","price","own","mins","goals","xg90","assists","xa90","xgi90","cs","dcP90","ict"])

/* ── LIVE / RESULTS MOCK DATA ───────────────────────────────── */
const GW_RESULTS=[
  {home:"ARS",away:"CHE",hs:2,as:1,scorers:["Saka 23'","Gabriel 67'"],assist:["Salah","Saliba"],key:4},
  {home:"LIV",away:"MUN",hs:3,as:0,scorers:["Salah 12'","Salah 55'","Jota 78'"],assist:["TAA","TAA","Salah"],key:1},
  {home:"MCI",away:"NEW",hs:1,as:2,scorers:["Haaland 34'","Isak 60'","Isak 88'"],assist:["Fernandes","Trippier","Gordon"],key:7},
  {home:"TOT",away:"AVL",hs:0,as:1,scorers:["Watkins 71'"],assist:["Cash"],key:6},
  {home:"BRE",away:"EVE",hs:2,as:0,scorers:["Mbeumo 14'","Wissa 58'"],assist:["Wissa","Mbeumo"],key:8},
]
const LIVE_MATCHES=[
  {id:1,home:"MCI",away:"BRI",hs:2,as:1,status:"FT",mins:90},
  {id:2,home:"ARS",away:"WOL",hs:1,as:0,status:"FT",mins:90},
  {id:3,home:"LIV",away:"BOU",hs:3,as:1,status:"LIVE",mins:82},
  {id:4,home:"TOT",away:"WHU",hs:0,as:0,status:"LIVE",mins:67},
  {id:5,home:"CHE",away:"EVE",hs:1,as:0,status:"LIVE",mins:34},
  {id:6,home:"NEW",away:"FUL",hs:null,as:null,status:"19:45",mins:0},
]
const LIVE_PTS={1:{pts:12,goals:1,assists:1,bonus:2,cs:0,mins:82},2:{pts:11,goals:1,bonus:1,cs:1,mins:90},26:{pts:9,saves:3,bonus:2,cs:1,mins:90},4:{pts:8,assists:1,cs:1,bonus:1,mins:90},18:{pts:7,cs:1,bonus:1,mins:90},19:{pts:7,cs:1,mins:90},16:{pts:6,cs:1,mins:90},17:{pts:5,mins:90},12:{pts:4,mins:67},8:{pts:2,mins:67},6:{pts:0,mins:34},27:{pts:0,mins:0},20:{pts:0,mins:0},10:{pts:2,mins:82},13:{pts:3,goals:1,mins:90}}

/* ── SQUAD / FORMATION ──────────────────────────────────────── */
const DEFAULT_SQUAD=[[26],[16,17,18,19],[1,4,8,12],[2,6]]
const DEFAULT_BENCH=[27,20,10,13]
const FORMATIONS={"4-4-2":[4,4,2],"4-3-3":[4,3,3],"4-5-1":[4,5,1],"3-4-3":[3,4,3],"3-5-2":[3,5,2],"5-4-1":[5,4,1],"5-3-2":[5,3,2],"5-2-3":[5,2,3]}
const applyFormation=(squad,bench,key)=>{
  const[nD,nM,nF]=FORMATIONS[key]
  const pool=[...squad.flat(),...bench].map(id=>PLmap[id]).filter(Boolean)
  const by={GK:[],DEF:[],MID:[],FWD:[]};pool.forEach(p=>by[p.pos]?.push(p))
  Object.values(by).forEach(a=>a.sort((x,y)=>y.nextGW-x.nextGW))
  const pick=(pos,n)=>by[pos].splice(0,n).map(p=>p.id)
  const gk=pick("GK",1),defs=pick("DEF",nD),mids=pick("MID",nM),fwds=pick("FWD",nF)
  const starters=[...gk,...defs,...mids,...fwds];if(starters.length<11)return null
  const used=new Set(starters)
  return{newSquad:[gk,defs,mids,fwds],newBench:pool.filter(p=>!used.has(p.id)).slice(0,4).map(p=>p.id)}
}

/* ════════════════════════════════════════════════════════
   PLAN BAR
════════════════════════════════════════════════════════ */
function PlanBar({squad,bench,captain,vc,bank,ft,chip,onChipChange}){
  const starters=squad.flat()
  const proj=useMemo(()=>{
    let t=starters.reduce((s,id)=>s+(PLmap[id]?.nextGW||0),0)
    const cp=PLmap[captain]?.nextGW||0;t+=cp
    if(chip==="bb")t+=bench.reduce((s,id)=>s+(PLmap[id]?.nextGW||0),0)
    if(chip==="tc")t+=cp*2
    return t.toFixed(1)
  },[starters,bench,captain,chip])
  return(
    <div style={{background:C3,borderBottom:`1px solid ${BD}`,padding:"7px 20px",display:"flex",gap:16,alignItems:"center",flexWrap:"wrap"}}>
      <div style={{display:"flex",alignItems:"baseline",gap:5}}>
        <span style={{fontSize:9,color:MU,textTransform:"uppercase",letterSpacing:"0.1em"}}>GW32 Est.</span>
        <span style={{fontSize:20,fontWeight:800,color:GR,...mn}}>{proj}</span>
        <span style={{fontSize:9,color:MU}}>pts</span>
      </div>
      <div style={{width:1,height:22,background:BD}}/>
      {[["FT",String(ft),ft>=2?GR:ft===1?AM:RD],["Bank",`£${bank.toFixed(1)}m`,AM],["Cap",PLmap[captain]?.name||"—",TX],["VC",PLmap[vc]?.name||"—",MU2]].map(([l,v,c])=>(
        <div key={l} style={{display:"flex",flexDirection:"column",gap:1}}>
          <span style={{fontSize:8,color:MU,textTransform:"uppercase",letterSpacing:"0.1em"}}>{l}</span>
          <span style={{fontSize:12,fontWeight:700,color:c,...mn}}>{v}</span>
        </div>
      ))}
      <div style={{marginLeft:"auto",display:"flex",alignItems:"center",gap:6}}>
        <span style={{fontSize:9,color:MU}}>CHIP:</span>
        <select value={chip||""} onChange={e=>onChipChange(e.target.value||null)} style={{background:C2,border:`1px solid ${BD}`,color:chip?AM:MU,borderRadius:4,padding:"3px 7px",fontSize:10,cursor:"pointer",fontFamily:"inherit"}}>
          {[["","No chip"],["wc","Wildcard"],["bb","Bench Boost"],["fh","Free Hit"],["tc","Triple Cap"]].map(([v,l])=><option key={v} value={v}>{l}</option>)}
        </select>
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════════════
   GW RESULTS PAGE
════════════════════════════════════════════════════════ */
function ResultsPage({
  gwLabel="Gameweek 31",
  resultsMatches=GW_RESULTS,
  liveMatches=LIVE_MATCHES,
  liveGwLabel="GW32",
  topScorers,
  topAssists,
}){
  const topG=(topScorers?.length?topScorers:[...PLAYERS].sort((a,b)=>b.goals-a.goals).slice(0,5))
  const topA=(topAssists?.length?topAssists:[...PLAYERS].sort((a,b)=>b.assists-a.assists).slice(0,5))
  return(
    <div style={{padding:"16px 20px",maxWidth:1300,margin:"0 auto"}}>
      <div style={{display:"flex",alignItems:"center",gap:16,marginBottom:16}}>
        <div>
          <div style={{fontSize:22,fontWeight:800,color:TX}}>{gwLabel} Results</div>
          <div style={{fontSize:12,color:MU}}>Premier League · 2025–26</div>
        </div>
        <div style={{marginLeft:"auto",display:"flex",gap:8}}>
          <Btn small variant="ghost">‹ GW30</Btn>
          <Btn small variant="primary">GW32 Fixtures ›</Btn>
        </div>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(230px,1fr))",gap:10,marginBottom:20}}>
        {resultsMatches.map((m,i)=>(
          <div key={m.id||i} style={cs({padding:"14px 16px"})}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:10}}>
              <span style={{fontSize:14,fontWeight:800,color:TX}}>{m.home}</span>
              <span style={{fontSize:20,fontWeight:900,color:TX,...mn}}>{m.hs}–{m.as}</span>
              <span style={{fontSize:14,fontWeight:800,color:TX}}>{m.away}</span>
            </div>
            <div style={{fontSize:10,color:MU}}>
              {(m.scorers||[]).map((s,j)=>(
                <div key={j} style={{display:"flex",alignItems:"center",gap:4,marginBottom:2}}>
                  <span style={{color:GR,fontSize:9}}>⚽</span><span>{s}</span>
                  {m.assist?.[j]&&<span style={{color:IN}}> (A: {m.assist[j]})</span>}
                </div>
              ))}
              {!m.scorers?.length&&<div style={{fontSize:10,color:MU}}>No scorer breakdown from endpoint.</div>}
            </div>
            {m.key&&PLmap[m.key]&&(
              <div style={{marginTop:8,paddingTop:6,borderTop:`1px solid ${BD}`,display:"flex",alignItems:"center",gap:6}}>
                <span style={{fontSize:9,color:AM}}>★ MOTM</span>
                <span style={{fontSize:11,fontWeight:700,color:TX}}>{PLmap[m.key].name}</span>
                <span style={{fontSize:10,color:GR,...mn}}>{n1(PLmap[m.key].nextGW)} pts</span>
              </div>
            )}
          </div>
        ))}
      </div>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:12}}>
        {/* Live GW32 */}
        <div style={cs()}>
          <div style={{padding:"10px 14px",borderBottom:`1px solid ${BD}`,display:"flex",alignItems:"center",gap:6}}>
            <span style={{width:7,height:7,borderRadius:"50%",background:GR,display:"inline-block"}}/>
            <span style={{fontSize:12,fontWeight:700,color:TX}}>{liveGwLabel} Live</span>
          </div>
          {liveMatches.map(m=>{
            const L=m.status==="LIVE",F=m.status==="FT"
            return(
              <div key={m.id} style={{padding:"9px 14px",borderBottom:`1px solid ${BD}18`,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <div style={{display:"flex",alignItems:"center",gap:6}}>
                  <div style={{width:6,height:6,borderRadius:"50%",background:L?GR:F?BD:MU,flexShrink:0}}/>
                  <span style={{fontSize:11,fontWeight:600,color:TX}}>{m.home}</span>
                </div>
                <span style={{fontSize:13,fontWeight:800,color:TX,...mn}}>{m.hs!=null?`${m.hs}–${m.as}`:"vs"}</span>
                <div style={{display:"flex",alignItems:"center",gap:5}}>
                  <span style={{fontSize:11,fontWeight:600,color:TX}}>{m.away}</span>
                  <span style={{fontSize:9,color:L?GR:F?MU:AM,fontWeight:700}}>{m.status}{L?"'":""}</span>
                </div>
              </div>
            )
          })}
        </div>
        {/* Top Scorers */}
        <div style={cs()}>
          <div style={{padding:"10px 14px",borderBottom:`1px solid ${BD}`,fontSize:12,fontWeight:700,color:TX}}>⚽ Top Scorers</div>
          {topG.map((p,i)=>(
            <div key={p.id} style={{padding:"8px 14px",borderBottom:`1px solid ${BD}18`,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
              <div style={{display:"flex",alignItems:"center",gap:8}}>
                <span style={{fontSize:10,color:MU,...mn,minWidth:14}}>{i+1}</span>
                <div><div style={{fontSize:12,fontWeight:700,color:TX}}>{p.name}</div><div style={{fontSize:9,color:MU}}>{p.team}</div></div>
              </div>
              <div style={{display:"flex",gap:8,alignItems:"center"}}>
                <span style={{fontSize:10,color:MU,...mn}}>xG {n2(p.xg)}</span>
                <span style={{fontSize:15,fontWeight:800,color:GR,...mn}}>{p.goals}</span>
              </div>
            </div>
          ))}
        </div>
        {/* Top Assists */}
        <div style={cs()}>
          <div style={{padding:"10px 14px",borderBottom:`1px solid ${BD}`,fontSize:12,fontWeight:700,color:TX}}>🅰 Top Assists</div>
          {topA.map((p,i)=>(
            <div key={p.id} style={{padding:"8px 14px",borderBottom:`1px solid ${BD}18`,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
              <div style={{display:"flex",alignItems:"center",gap:8}}>
                <span style={{fontSize:10,color:MU,...mn,minWidth:14}}>{i+1}</span>
                <div><div style={{fontSize:12,fontWeight:700,color:TX}}>{p.name}</div><div style={{fontSize:9,color:MU}}>{p.team}</div></div>
              </div>
              <div style={{display:"flex",gap:8,alignItems:"center"}}>
                <span style={{fontSize:10,color:MU,...mn}}>xA {n2(p.xa)}</span>
                <span style={{fontSize:15,fontWeight:800,color:IN,...mn}}>{p.assists}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════════════
   PLAYER ANALYTICS — full scrollable stat table
════════════════════════════════════════════════════════ */
function AnalyticsPage({onAddCompare,compareList,shortlist,setShortlist,playersData=PLAYERS}){
  const [sort,setSort]=useState({col:"pts5GW",dir:-1})
  const [pos,setPos]=useState("ALL")
  const [query,setQuery]=useState("")
  const [maxPrice,setMax]=useState(15)
  const [avail,setAv]=useState(false)
  const [teamF,setTeamF]=useState("")
  const [activeGrp,setAG]=useState("predict")
  const [vis,setVis]=useState(DEFAULT_VIS)
  const [colMenu,setCM]=useState(false)
  const [drawer,setDrawer]=useState(null)

  const cols=useMemo(()=>{
    const always=new Set(["nextGW","pts5GW","price","own"])
    return ALL_COLS.filter(c=>always.has(c.id)||(vis.has(c.id)&&(activeGrp==="all"||c.grp===activeGrp)))
  },[vis,activeGrp])

  const teams=useMemo(()=>[
    ...new Set((playersData||PLAYERS).map(p=>p.team).filter(Boolean)),
  ].sort(),[playersData])

  const sorted=useMemo(()=>{
    let d=playersData?.length?playersData:PLAYERS
    if(pos!=="ALL") d=d.filter(p=>p.pos===pos)
    if(avail) d=d.filter(p=>p.isAvail)
    if(query) d=d.filter(p=>p.name.toLowerCase().includes(query.toLowerCase())||p.team.toLowerCase().includes(query.toLowerCase()))
    if(maxPrice<15) d=d.filter(p=>p.price<=maxPrice)
    if(teamF) d=d.filter(p=>p.team===teamF)
    return[...d].sort((a,b)=>(b[sort.col]-a[sort.col])*sort.dir)
  },[playersData,pos,avail,query,maxPrice,teamF,sort])

  const rowsById=useMemo(()=>Object.fromEntries(sorted.map(p=>[p.id,p])),[sorted])

  const toggleVis=id=>setVis(v=>{const n=new Set(v);n.has(id)?n.delete(id):n.add(id);return n})

  return(
    <div style={{padding:"16px 20px",maxWidth:"100%",margin:"0 auto",position:"relative"}}>
      {/* Filters */}
      <div style={{display:"flex",gap:8,marginBottom:10,flexWrap:"wrap",alignItems:"center"}}>
        <div style={{position:"relative",flex:"0 0 165px"}}>
          <Search size={12} style={{position:"absolute",left:9,top:"50%",transform:"translateY(-50%)",color:MU}}/>
          <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search…"
            style={{width:"100%",padding:"6px 10px 6px 27px",background:C2,border:`1px solid ${BD}`,borderRadius:5,color:TX,fontSize:12,boxSizing:"border-box"}}/>
        </div>
        {["ALL","GK","DEF","MID","FWD"].map(p=>(
          <Btn key={p} small variant={pos===p?"primary":"ghost"} onClick={()=>setPos(p)}>{p}</Btn>
        ))}
        <select value={teamF} onChange={e=>setTeamF(e.target.value)} style={{background:C2,border:`1px solid ${BD}`,color:teamF?TX:MU,borderRadius:4,padding:"4px 8px",fontSize:11,cursor:"pointer",fontFamily:"inherit"}}>
          <option value="">All Teams</option>
          {teams.map(t=><option key={t} value={t}>{t}</option>)}
        </select>
        <div style={{display:"flex",alignItems:"center",gap:5,marginLeft:"auto"}}>
          <span style={{fontSize:11,color:MU}}>≤ £{maxPrice}m</span>
          <input type="range" min={4} max={15} step={0.5} value={maxPrice} onChange={e=>setMax(+e.target.value)} style={{width:70,accentColor:ACT}}/>
        </div>
        <label style={{display:"flex",alignItems:"center",gap:4,fontSize:11,color:MU,cursor:"pointer"}}>
          <input type="checkbox" checked={avail} onChange={e=>setAv(e.target.checked)} style={{accentColor:ACT}}/> Available
        </label>
      </div>
      {/* Group tabs */}
      <div style={{display:"flex",borderBottom:`1px solid ${BD}`,alignItems:"center",marginBottom:0}}>
        {[{id:"all",l:"All Stats"},...GRPS.map(g=>({id:g.id,l:g.l}))].map(g=>(
          <Btn key={g.id} variant="tab" active={activeGrp===g.id} onClick={()=>setAG(g.id)}>{g.l}</Btn>
        ))}
        <div style={{marginLeft:"auto",position:"relative"}}>
          <Btn small variant="ghost" onClick={()=>setCM(v=>!v)} style={{margin:"8px 0"}}><Settings size={11}/> Columns</Btn>
          {colMenu&&(
            <div style={{position:"absolute",right:0,top:"calc(100%+2px)",background:C2,border:`1px solid ${BD}`,borderRadius:7,zIndex:200,padding:"12px 14px",minWidth:280,maxHeight:380,overflowY:"auto"}}>
              {GRPS.map(g=>(
                <div key={g.id} style={{marginBottom:10}}>
                  <div style={{fontSize:9,color:MU2,textTransform:"uppercase",letterSpacing:"0.08em",marginBottom:5}}>{g.l}</div>
                  <div style={{display:"flex",flexWrap:"wrap",gap:4}}>
                    {ALL_COLS.filter(c=>c.grp===g.id).map(c=>(
                      <button key={c.id} onClick={()=>toggleVis(c.id)} style={{background:vis.has(c.id)?ACT+"22":"transparent",color:vis.has(c.id)?ACT:MU,border:`1px solid ${vis.has(c.id)?ACT+"44":BD}`,borderRadius:3,padding:"2px 7px",fontSize:10,cursor:"pointer",fontFamily:"inherit"}}>
                        {c.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      {/* Table */}
      <div style={{overflowX:"auto",maxHeight:"calc(100vh - 300px)",overflowY:"auto"}}>
        <table style={{width:"100%",borderCollapse:"collapse"}}>
          <thead>
            <tr>
              <th style={{...TH,paddingLeft:14,minWidth:22}}>#</th>
              <th style={{...TH,minWidth:140}}>Player</th>
              <th style={TH}>Pos</th>
              <th style={{...TH,minWidth:130}}>Next Fixtures</th>
              {cols.map(c=><SortTH key={c.id+c.label} col={c.id} label={c.label} sort={sort} setSort={setSort} right/>)}
              <th style={{...TH,textAlign:"center"}}>Trend</th>
              <th style={TH}></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p,i)=>{
              const inS=shortlist.includes(p.id),inC=compareList.includes(p.id)
              const canCompare=Boolean(PLmap[p.id])
              return(
                <tr key={p.id} style={{cursor:"pointer",transition:"background 0.1s",background:drawer===p.id?C2:"transparent"}}
                  onMouseEnter={e=>e.currentTarget.style.background=C2}
                  onMouseLeave={e=>e.currentTarget.style.background=drawer===p.id?C2:"transparent"}>
                  <td style={{...TD,fontSize:10,color:MU,paddingLeft:14,...mn}}>{i+1}</td>
                  <td style={TD} onClick={()=>setDrawer(drawer===p.id?null:p.id)}>
                    <div style={{fontWeight:700,fontSize:13}}>{p.name}</div>
                    <div style={{fontSize:9,color:MU}}>{p.team} · {n1(p.own)}% sel</div>
                  </td>
                  <td style={TD}><span style={ptag(p.pos)}>{p.pos}</span></td>
                  <td style={TD}>
                    <div style={{display:"flex",gap:3}}>
                      {p.fdrs.map((f,fi)=>(
                        <div key={fi} style={{textAlign:"center"}}>
                          <span style={{...fdp(f),fontSize:8,padding:"1px 3px",minWidth:26,display:"block"}}>{p.opps[fi]?.split(" ")[0]}</span>
                          <div style={{fontSize:7,color:FDR_T[f]||MU,marginTop:1}}>{p.opps[fi]?.includes("(H)")?"H":"A"}</div>
                        </div>
                      ))}
                    </div>
                  </td>
                  {cols.map(c=>{
                    const v=p[c.id]??0,clr=typeof c.color==="function"?c.color(v):TX
                    return<td key={c.id+c.label} style={{...TD,textAlign:"right",...mn,color:clr,fontWeight:c.bold?700:400}}>{c.fmt(v)}</td>
                  })}
                  <td style={{...TD,textAlign:"center"}}><Spark data={p.history||[]} color={p.form>=6?GR:IN}/></td>
                  <td style={TD}>
                    <div style={{display:"flex",gap:3}}>
                      <Btn small variant={inS?"amber":"ghost"} onClick={()=>setShortlist(s=>inS?s.filter(x=>x!==p.id):[...s,p.id])}><Star size={9}/></Btn>
                      <Btn small variant={inC?"primary":"ghost"} onClick={()=>onAddCompare(p.id)} disabled={!canCompare}><Users size={9}/></Btn>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div style={{fontSize:10,color:MU,marginTop:6}}>{sorted.length} players · {cols.length} columns · ★ shortlist · ⊞ compare</div>
      {/* Side drawer */}
      {drawer&&rowsById[drawer]&&(
        <div style={{position:"fixed",right:0,top:48,bottom:0,width:290,background:CARD,borderLeft:`1px solid ${BD}`,zIndex:200,overflowY:"auto"}}>
          <DrawerContent p={rowsById[drawer]} onClose={()=>setDrawer(null)} onCompare={()=>{if(PLmap[drawer])onAddCompare(drawer);setDrawer(null)}}/>
        </div>
      )}
    </div>
  )
}

function DrawerContent({p,onClose,onCompare}){
  const fd=GW_NEXT.map((gw,i)=>({gw,pts:p.gwPreds[i]||0,opp:p.opps[i]||"BGW",fdr:p.fdrs[i]||3}))
  return(
    <div>
      <div style={{padding:"12px 14px",borderBottom:`1px solid ${BD}`,display:"flex",alignItems:"center",gap:8}}>
        <span style={ptag(p.pos)}>{p.pos}</span>
        <div style={{flex:1}}><div style={{fontWeight:700,fontSize:14,color:TX}}>{p.name}</div><div style={{fontSize:10,color:MU}}>{p.team} · £{n1(p.price)}m · {n1(p.own)}% sel</div></div>
        <Btn small variant="ghost" onClick={onClose}><X size={11}/></Btn>
      </div>
      <div style={{padding:"10px 14px",borderBottom:`1px solid ${BD}`}}>
        {[["GW32 Pred",`${n1(p.nextGW)} pts`,GR,true],["5GW Proj",`${n1(p.pts5GW)} pts`,GR,false],["xGI/90",p.pos==="GK"?"—":n2(p.xgi90),TX,false],["xG/90",p.pos==="GK"?"—":n2(p.xg90),TX,false],["xA/90",p.pos==="GK"?"—":n2(p.xa90),TX,false],["ICT",n1(p.ict),p.ict>=50?GR:TX,false],["DC/90",n2(p.dcP90),p.dcP90>=3?GR:TX,false],["CBI",n2(p.cbi),TX,false],["Form",n1(p.form),p.form>=7?GR:TX,false],["Mins%",`${Math.round(p.minRel*100)}%`,TX,false]].map(([l,v,c,b])=>(
          <div key={l} style={{display:"flex",justifyContent:"space-between",padding:"4px 0",borderBottom:`1px solid ${BD}20`}}>
            <span style={{fontSize:11,color:MU}}>{l}</span><span style={{fontSize:12,fontWeight:b?800:600,color:c,...mn}}>{v}</span>
          </div>
        ))}
      </div>
      <div style={{padding:"10px 14px",borderBottom:`1px solid ${BD}`}}>
        <div style={{fontSize:10,color:MU,marginBottom:6}}>Form · last 15 GWs</div>
        <Spark data={p.history} color={GR} w={258} h={40}/>
      </div>
      <div style={{padding:"10px 14px",borderBottom:`1px solid ${BD}`}}>
        <div style={{fontSize:10,color:MU,marginBottom:6}}>Next 5 GW projection</div>
        {fd.map((d,i)=>(
          <div key={i} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"4px 0"}}>
            <span style={{...fdp(d.fdr),fontSize:9,minWidth:68,padding:"2px 4px"}}>{d.opp}</span>
            <span style={{fontSize:12,fontWeight:700,color:GR,...mn}}>{n1(d.pts)}</span>
          </div>
        ))}
      </div>
      <div style={{padding:"10px 14px"}}>
        <Btn variant="primary" onClick={onCompare} disabled={!PLmap[p.id]} style={{width:"100%",justifyContent:"center"}}><Users size={12}/> Compare</Btn>
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════════════
   FIXTURES PAGE
════════════════════════════════════════════════════════ */
function FixturesPage({tickerRows,analyticsRows=PLAYERS}){
  const [mode,setMode]=useState("overall")
  const teams=useMemo(()=>{
    if(tickerRows?.length){
      return tickerRows.map(t=>{
        const fx=t.fixtures||[]
        return{
          code:t.code,
          fixtures:fx,
          fdrAvg:+(fx.reduce((s,f)=>s+(f.f||3),0)/Math.max(fx.length,1)).toFixed(1),
          aFdrAvg:+(fx.reduce((s,f)=>s+((f.af||f.f)||3),0)/Math.max(fx.length,1)).toFixed(1),
          dFdrAvg:+(fx.reduce((s,f)=>s+((f.df||f.f)||3),0)/Math.max(fx.length,1)).toFixed(1),
        }
      })
    }
    return Object.entries(TF).map(([code,fx])=>({code,fixtures:fx,fdrAvg:+(fx.reduce((s,f)=>s+f.f,0)/fx.length).toFixed(1),aFdrAvg:+(fx.reduce((s,f)=>s+(f.af||f.f),0)/fx.length).toFixed(1),dFdrAvg:+(fx.reduce((s,f)=>s+(f.df||f.f),0)/fx.length).toFixed(1)}))
  },[tickerRows])
  const getF=(t,i)=>mode==="attack"?t.fixtures[i]?.af:mode==="defence"?t.fixtures[i]?.df:t.fixtures[i]?.f
  const getAvg=t=>mode==="attack"?t.aFdrAvg:mode==="defence"?t.dFdrAvg:t.fdrAvg
  const sorted=[...teams].sort((a,b)=>getAvg(a)-getAvg(b))
  return(
    <div style={{padding:"16px 20px",maxWidth:1200,margin:"0 auto"}}>
      <div style={{display:"flex",gap:8,marginBottom:14,alignItems:"center"}}>
        <div><div style={{fontSize:18,fontWeight:800,color:TX}}>Fixture Difficulty Ratings</div><div style={{fontSize:11,color:MU}}>GW32–36 · Easiest first</div></div>
        <div style={{marginLeft:"auto",display:"flex",gap:6}}>
          {[["overall","Overall"],["attack","Attack FDR"],["defence","Defence FDR"]].map(([id,l])=>(
            <Btn key={id} small variant={mode===id?"primary":"ghost"} onClick={()=>setMode(id)}>{l}</Btn>
          ))}
        </div>
      </div>
      <div style={{display:"flex",gap:10,marginBottom:12}}>
        {[1,2,3,4,5].map(f=>(
          <div key={f} style={{display:"flex",alignItems:"center",gap:4}}>
            <div style={{width:12,height:12,borderRadius:2,background:FDR_B[f]}}/>
            <span style={{fontSize:10,color:MU}}>{{1:"Very Easy",2:"Easy",3:"Medium",4:"Hard",5:"Very Hard"}[f]}</span>
          </div>
        ))}
      </div>
      <div style={cs({overflowX:"auto"})}>
        <table style={{width:"100%",borderCollapse:"collapse"}}>
          <thead><tr>
            <th style={{...TH,textAlign:"center",minWidth:48}}>Pos</th>
            <th style={{...TH,minWidth:70}}>Team</th>
            <th style={{...TH,textAlign:"center"}}>Avg</th>
            {GW_NEXT.map(gw=><th key={gw} style={{...TH,textAlign:"center",minWidth:98}}>{gw}</th>)}
            <th style={{...TH,textAlign:"center"}}>Best GW</th>
          </tr></thead>
          <tbody>
            {sorted.map((team,idx)=>{
              const fdrs=GW_NEXT.map((_,i)=>getF(team,i)||3)
              const best=fdrs.reduce((bi,f,i,a)=>f<a[bi]?i:bi,0)
              const avg=getAvg(team)
              return(
                <tr key={team.code} onMouseEnter={e=>e.currentTarget.style.background=C2} onMouseLeave={e=>e.currentTarget.style.background="transparent"} style={{transition:"background 0.1s",cursor:"pointer"}}>
                  <td style={{...TD,textAlign:"center",fontWeight:800,color:MU2,...mn}}>{idx+1}</td>
                  <td style={{...TD,fontWeight:700}}>{team.code}</td>
                  <td style={{...TD,textAlign:"center",...mn,fontWeight:700,color:avg<=2?GR:avg>=4?RD:TX}}>{avg}</td>
                  {fdrs.map((f,i)=>(
                    <td key={i} style={{padding:"5px 6px",borderBottom:`1px solid ${BD}18`,textAlign:"center"}}>
                      <div style={{background:FDR_B[f],color:FDR_T[f],padding:"5px 6px",borderRadius:4,fontSize:10,fontWeight:700,display:"inline-block",minWidth:76,lineHeight:1.35}}>
                        <div>{team.fixtures[i]?.o}</div>
                        <div style={{fontSize:8,opacity:.85}}>{team.fixtures[i]?.h?"HOME":"AWAY"}</div>
                      </div>
                    </td>
                  ))}
                  <td style={{...TD,textAlign:"center"}}><span style={{background:GR+"18",color:GR,borderRadius:3,padding:"2px 6px",fontSize:10,fontWeight:700}}>{GW_NEXT[best]}</span></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginTop:14}}>
        {[{title:"Best attack windows ⚡",col:"aFdrAvg",pf:["MID","FWD"]},{title:"Best CS prospects 🛡",col:"dFdrAvg",pf:["GK","DEF"]}].map(({title,col,pf})=>(
          <div key={title} style={cs({padding:"12px 14px"})}>
            <div style={{fontSize:12,fontWeight:700,color:TX,marginBottom:10}}>{title}</div>
            {[...teams].sort((a,b)=>a[col]-b[col]).slice(0,5).map((t,i)=>{
              const pool=(analyticsRows?.length?analyticsRows:PLAYERS)
              const best=pool.filter(p=>p.team===t.code&&pf.includes(p.pos)).sort((a,b)=>b.pts5GW-a.pts5GW)[0]
              return(
                <div key={t.code} style={{display:"flex",alignItems:"center",gap:8,padding:"5px 0",borderBottom:`1px solid ${BD}22`}}>
                  <span style={{fontSize:10,color:MU,...mn,minWidth:14}}>{i+1}</span>
                  <span style={{fontWeight:700,color:GR,minWidth:36,fontSize:12}}>{t.code}</span>
                  <span style={{fontSize:10,color:MU,flex:1}}>Avg {t[col]}</span>
                  <span style={{fontSize:11,color:TX}}>{best?.name||"—"}</span>
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════════════
   COMPARE PAGE
════════════════════════════════════════════════════════ */
const RADAR_AX={
  GK: [{k:"form",m:10,l:"Form"},{k:"minRel",m:1,l:"Minutes"},{k:"pts5GW",m:32,l:"5GW"},{k:"ict",m:40,l:"ICT"},{k:"dcP90",m:2,l:"DC/90"},{k:"nextGW",m:8,l:"Next GW"}],
  DEF:[{k:"xgi90",m:0.5,l:"xGI/90"},{k:"form",m:8,l:"Form"},{k:"minRel",m:1,l:"Minutes"},{k:"pts5GW",m:34,l:"5GW"},{k:"dcP90",m:5,l:"DC/90"},{k:"ict",m:60,l:"ICT"}],
  MID:[{k:"xgi90",m:0.9,l:"xGI/90"},{k:"xg90",m:0.5,l:"xG/90"},{k:"xa90",m:0.4,l:"xA/90"},{k:"form",m:10,l:"Form"},{k:"minRel",m:1,l:"Minutes"},{k:"ict",m:80,l:"ICT"}],
  FWD:[{k:"xgi90",m:1.1,l:"xGI/90"},{k:"xg90",m:1.0,l:"xG/90"},{k:"form",m:9,l:"Form"},{k:"pts5GW",m:40,l:"5GW"},{k:"minRel",m:1,l:"Minutes"},{k:"ict",m:70,l:"ICT"}],
}
function ComparePage({compareList,setCompareList}){
  const [adding,setAdding]=useState("")
  const ps=compareList.map(id=>PLmap[id]).filter(Boolean)
  const CC=[ACT,GR,AM,IN]
  const rem=id=>setCompareList(l=>l.filter(x=>x!==id))
  const add=id=>{const n=+id;if(n&&!compareList.includes(n)&&compareList.length<4){setCompareList(l=>[...l,n]);setAdding("")}}
  const pos=ps[0]?.pos||"MID",axes=RADAR_AX[pos]||RADAR_AX.MID
  const radar=axes.map(ax=>({stat:ax.l,...ps.reduce((acc,p)=>({...acc,[p.name]:+Math.min(100,((p[ax.k]||0)/ax.m)*100).toFixed(1)}),{})}))
  const rolling=GW_LBLS.map((gw,i)=>({gw,...ps.reduce((acc,p)=>({...acc,[p.name]:p.history[i]}),{})}))
  if(!ps.length)return<div style={{padding:"40px",textAlign:"center",color:MU}}>No players — go to Player Stats and click ⊞</div>
  return(
    <div style={{padding:"16px 20px",maxWidth:1200,margin:"0 auto"}}>
      <div style={{display:"flex",gap:10,marginBottom:14,flexWrap:"wrap",alignItems:"center"}}>
        {ps.map((p,i)=>(
          <div key={p.id} style={{...c2s(),padding:"8px 12px",display:"flex",alignItems:"center",gap:8,borderLeft:`3px solid ${CC[i]}`}}>
            <span style={ptag(p.pos)}>{p.pos}</span>
            <div><div style={{fontWeight:700,fontSize:13,color:TX}}>{p.name}</div><div style={{fontSize:10,color:MU}}>{p.team} · £{n1(p.price)}m</div></div>
            <Btn small variant="ghost" onClick={()=>rem(p.id)}><X size={10}/></Btn>
          </div>
        ))}
        {ps.length<4&&(
          <select value={adding} onChange={e=>add(e.target.value)} style={{background:C2,border:`1px dashed ${BD2}`,color:MU,borderRadius:5,padding:"7px 10px",fontSize:12,cursor:"pointer",fontFamily:"inherit"}}>
            <option value="">+ Add player…</option>
            {PLAYERS.filter(p=>!compareList.includes(p.id)).map(p=><option key={p.id} value={p.id}>{p.name} ({p.pos} · {p.team})</option>)}
          </select>
        )}
      </div>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14,marginBottom:14}}>
        <div style={cs({padding:"14px 16px"})}>
          <div style={{fontSize:11,color:MU,marginBottom:10}}>Full stats · {pos} frame</div>
          {[{l:"GW32 Pred",k:"nextGW",f:n1},{l:"5GW Proj",k:"pts5GW",f:n1},{l:"Form",k:"form",f:n1},{l:"xGI/90",k:"xgi90",f:n2},{l:"xG/90",k:"xg90",f:n2},{l:"xA/90",k:"xa90",f:n2},{l:"Goals",k:"goals",f:ni},{l:"GI/90",k:"gi90",f:n2},{l:"xGI",k:"xgi",f:n2},{l:"Assists",k:"assists",f:ni},{l:"CS",k:"cs",f:ni},{l:"xGC",k:"xgc",f:n2},{l:"DC/90",k:"dcP90",f:n2},{l:"CBI",k:"cbi",f:n2},{l:"ICT",k:"ict",f:n1},{l:"Influence",k:"infl",f:n1},{l:"Creativity",k:"cre",f:n1},{l:"Threat",k:"thr",f:n1},{l:"Price",k:"price",f:v=>`£${n1(v)}m`},{l:"Ownership",k:"own",f:v=>`${n1(v)}%`},{l:"Min%",k:"minRel",f:v=>`${ni(v*100)}%`},{l:"Value",k:"valueScore",f:n2}].map(row=>{
            const vals=ps.map(p=>p[row.k]||0),mx=Math.max(...vals)
            return(
              <div key={row.l} style={{display:"flex",alignItems:"center",gap:6,padding:"4px 0",borderBottom:`1px solid ${BD}22`}}>
                <span style={{fontSize:10,color:MU,minWidth:110}}>{row.l}</span>
                {ps.map((p,i)=>{const v=p[row.k]||0,top=v===mx&&v>0;return<span key={p.id} style={{fontSize:11,fontWeight:top?800:400,...mn,color:top?CC[i]:MU2,minWidth:58}}>{row.f(v)}</span>})}
              </div>
            )
          })}
        </div>
        <div style={cs({padding:"14px 16px"})}>
          <div style={{fontSize:11,color:MU,marginBottom:4}}>{pos} radar · position-specific axes</div>
          <ResponsiveContainer width="100%" height={270}>
            <RadarChart data={radar}>
              <PolarGrid stroke={BD}/><PolarAngleAxis dataKey="stat" tick={{fontSize:9,fill:MU}}/><PolarRadiusAxis tick={false} axisLine={false}/>
              {ps.map((p,i)=><Radar key={p.id} dataKey={p.name} stroke={CC[i]} fill={CC[i]} fillOpacity={0.1} strokeWidth={2}/>)}
            </RadarChart>
          </ResponsiveContainer>
          <div style={{display:"flex",gap:10,justifyContent:"center",marginTop:4}}>
            {ps.map((p,i)=><span key={p.id} style={{display:"flex",alignItems:"center",gap:4,fontSize:10,color:CC[i]}}><span style={{width:10,height:10,borderRadius:2,background:CC[i],display:"inline-block"}}/>{p.name}</span>)}
          </div>
        </div>
      </div>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
        <div style={cs({padding:"14px 16px"})}>
          <div style={{fontSize:11,color:MU,marginBottom:8}}>Points per GW · last 15</div>
          <ResponsiveContainer width="100%" height={145}>
            <LineChart data={rolling} margin={{top:4,right:4,bottom:0,left:-14}}>
              <CartesianGrid strokeDasharray="3 3" stroke={BD} vertical={false}/><XAxis dataKey="gw" tick={{fontSize:8,fill:MU}} interval={2}/><YAxis tick={{fontSize:8,fill:MU}}/><Tooltip content={<CT/>}/>
              {ps.map((p,i)=><Line key={p.id} type="monotone" dataKey={p.name} stroke={CC[i]} strokeWidth={2} dot={false}/>)}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div style={cs({padding:"14px 16px"})}>
          <div style={{fontSize:11,color:MU,marginBottom:8}}>Fixture comparison</div>
          <table style={{width:"100%",borderCollapse:"collapse"}}>
            <thead><tr><th style={TH}>GW</th>{ps.map((p,i)=><th key={p.id} style={{...TH,color:CC[i]}}>{p.name}</th>)}</tr></thead>
            <tbody>
              {GW_NEXT.map((gw,gi)=>(
                <tr key={gw}>
                  <td style={{...TD,fontWeight:700,color:MU,fontSize:10}}>{gw}</td>
                  {ps.map(p=>(
                    <td key={p.id} style={TD}>
                      <div style={{display:"flex",alignItems:"center",gap:5}}>
                        <span style={{...fdp(p.fdrs[gi]),fontSize:9,minWidth:56,padding:"2px 3px"}}>{p.opps[gi]||"BGW"}</span>
                        <span style={{fontSize:11,color:GR,...mn}}>{n1(p.gwPreds[gi])}</span>
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
              <tr style={{background:C2}}>
                <td style={{...TD,fontWeight:700,color:MU}}>Total</td>
                {ps.map(p=><td key={p.id} style={{...TD,...mn,fontWeight:800,color:GR}}>{n1(p.pts5GW)}</td>)}
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════════════
   PITCH CARD
════════════════════════════════════════════════════════ */
function PCard({id,captain,vc,sel,bench,onSel,onCap,onVc}){
  const p=PLmap[id];if(!p)return null
  const iC=captain===id,iV=vc===id
  return(
    <div onClick={onSel} style={{background:sel?C3:CARD,border:`1px solid ${sel?ACT:iC?AM:iV?MU2:BD}`,borderRadius:6,padding:"7px 8px",cursor:"pointer",width:bench?80:92,textAlign:"center",position:"relative",transition:"border 0.12s"}}>
      {iC&&<div style={{position:"absolute",top:-7,left:"50%",transform:"translateX(-50%)",background:AM,color:"#000",borderRadius:3,fontSize:8,fontWeight:800,padding:"0 4px"}}>C</div>}
      {iV&&<div style={{position:"absolute",top:-7,left:"50%",transform:"translateX(-50%)",background:MU2,color:"#fff",borderRadius:3,fontSize:8,fontWeight:800,padding:"0 4px"}}>VC</div>}
      <div style={{fontSize:8,color:MU,marginBottom:2}}>{p.team}</div>
      <div style={{fontSize:bench?10:11,fontWeight:700,color:sel?ACT:TX,marginBottom:3,lineHeight:1.2}}>{p.name}</div>
      <div style={{fontSize:12,fontWeight:800,color:GR,...mn,marginBottom:4}}>{n1(p.nextGW)}</div>
      <FDRStrip fdrs={p.fdrs} size={bench?8:9}/>
      <div style={{display:"flex",gap:3,marginTop:4,justifyContent:"center"}}>
        <button onClick={e=>{e.stopPropagation();onCap()}} style={{fontSize:7,background:iC?AM+"33":"transparent",color:iC?AM:MU,border:`1px solid ${iC?AM:BD}`,borderRadius:2,padding:"1px 3px",cursor:"pointer"}}>C</button>
        <button onClick={e=>{e.stopPropagation();onVc()}} style={{fontSize:7,background:iV?MU2+"33":"transparent",color:iV?MU2:MU,border:`1px solid ${iV?MU2:BD}`,borderRadius:2,padding:"1px 3px",cursor:"pointer"}}>VC</button>
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════════════
   PLANNER PAGE
════════════════════════════════════════════════════════ */
function PlannerPage({squad,setSquad,bench,setBench,captain,setCaptain,vc,setVc,bank,setBank,ft,setFt,chip,setPage}){
  const [selId,setSelId]=useState(null)
  const [form,setForm]=useState("4-4-2")
  const [showF,setSF]=useState(false)
  const starters=squad.flat(),inSquad=new Set([...starters,...bench])
  const selP=selId?PLmap[selId]:null
  const cands=useMemo(()=>{
    if(!selP)return[]
    const bgt=bank+selP.sellPrice
    return PLAYERS.filter(p=>p.pos===selP.pos&&!inSquad.has(p.id)&&p.price<=bgt&&p.isAvail).sort((a,b)=>b.pts5GW-a.pts5GW).slice(0,8).map(p=>({...p,gain:+(p.pts5GW-selP.pts5GW).toFixed(1)}))
  },[selP,bank,starters,bench])
  const applyF=key=>{const r=applyFormation(squad,bench,key);if(r){setSquad(r.newSquad);setBench(r.newBench);setForm(key);setSF(false);setSelId(null)}}
  const doReplace=(outId,inId)=>{
    const pO=PLmap[outId],pI=PLmap[inId];if(!pO||!pI)return
    setBank(b=>+(b-(pI.price-pO.sellPrice)).toFixed(1));setFt(f=>Math.max(0,f-1))
    setSquad(s=>s.map(r=>r.map(id=>id===outId?inId:id)));setBench(b=>b.map(id=>id===outId?inId:id));setSelId(null)
  }
  const gwP=GW_NEXT.map((_,i)=>({gw:GW_NEXT[i],pts:+starters.reduce((s,id)=>{const p=PLmap[id];return s+(p?+(p.nextGW*(1+(3-(p.fdrs[i]||3))*0.08)).toFixed(1):0)},0).toFixed(1)}))
  return(
    <div style={{padding:"16px 20px",maxWidth:1300,margin:"0 auto"}}>
      <div style={{display:"grid",gridTemplateColumns:"1fr 316px",gap:16}}>
        <div>
          <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:12}}>
            <div style={{position:"relative"}}>
              <Btn variant="ghost" onClick={()=>setSF(v=>!v)} style={{minWidth:100,justifyContent:"space-between"}}>{form} <ChevronDown size={11}/></Btn>
              {showF&&(
                <div style={{position:"absolute",top:"calc(100%+4px)",left:0,background:C2,border:`1px solid ${BD}`,borderRadius:6,zIndex:50,overflow:"hidden",minWidth:130}}>
                  {Object.keys(FORMATIONS).map(f=>(
                    <div key={f} onClick={()=>applyF(f)} style={{padding:"7px 14px",cursor:"pointer",fontSize:12,fontWeight:600,color:f===form?ACT:TX,background:f===form?ACT+"15":"transparent"}} onMouseEnter={e=>e.currentTarget.style.background=C3} onMouseLeave={e=>e.currentTarget.style.background=f===form?ACT+"15":"transparent"}>{f}</div>
                  ))}
                </div>
              )}
            </div>
            <span style={{fontSize:11,color:MU}}>{selId?`Replacing ${PLmap[selId]?.name}`:"Click a player to swap"}</span>
            {selId&&<Btn small variant="ghost" onClick={()=>setSelId(null)}><X size={10}/> Cancel</Btn>}
          </div>
          <div style={{background:"#071a0d",border:`1px solid #193523`,borderRadius:10,padding:"14px 10px",position:"relative",overflow:"hidden"}}>
            <div style={{position:"absolute",inset:0,opacity:0.05,pointerEvents:"none"}}>
              <div style={{position:"absolute",left:"50%",top:0,bottom:0,width:1,background:"#fff"}}/>
              <div style={{position:"absolute",left:"10%",right:"10%",top:"42%",height:"16%",border:"1px solid #fff",borderRadius:"50%"}}/>
            </div>
            {squad.map((row,ri)=>(
              <div key={ri} style={{display:"flex",justifyContent:"center",gap:8,marginBottom:12}}>
                {row.map(id=><PCard key={id} id={id} captain={captain} vc={vc} sel={selId===id} bench={false} onSel={()=>setSelId(selId===id?null:id)} onCap={()=>setCaptain(id)} onVc={()=>setVc(id)}/>)}
              </div>
            ))}
            <div style={{borderTop:`1px dashed #193523`,paddingTop:10,display:"flex",justifyContent:"center",gap:8}}>
              {bench.map(id=><PCard key={id} id={id} captain={captain} vc={vc} sel={selId===id} bench onSel={()=>setSelId(selId===id?null:id)} onCap={()=>setCaptain(id)} onVc={()=>setVc(id)}/>)}
            </div>
          </div>
        </div>
        <div style={{display:"flex",flexDirection:"column",gap:12}}>
          <div style={cs()}>
            <div style={{padding:"10px 14px",borderBottom:`1px solid ${BD}`,display:"flex",gap:6,alignItems:"center"}}>
              <RefreshCw size={12} style={{color:ACT}}/><span style={{fontSize:12,fontWeight:700,color:TX}}>{selP?`Replacing ${selP.name}`:"Transfer Centre"}</span>
            </div>
            {!selP?(
              <div style={{padding:"16px 14px",textAlign:"center"}}>
                <div style={{color:MU,fontSize:12,marginBottom:12}}>Select a player on the pitch</div>
                <Btn variant="primary" onClick={()=>setPage("analytics")}><Search size={12}/> Browse Players</Btn>
              </div>
            ):(
              <div style={{padding:"10px 14px"}}>
                <div style={{...c2s({padding:"8px 11px",marginBottom:8,borderLeft:`3px solid ${RD}`})}}>
                  <div style={{display:"flex",justifyContent:"space-between"}}>
                    <div><span style={{fontSize:10,color:RD}}>OUT · </span><span style={{fontWeight:700,fontSize:12,color:TX}}>{selP.name}</span></div>
                    <div style={{textAlign:"right"}}><div style={{fontSize:11,...mn,color:AM}}>£{n1(selP.sellPrice)}m</div><div style={{fontSize:9,color:MU}}>{n1(selP.pts5GW)} 5GW</div></div>
                  </div>
                  <div style={{marginTop:4}}><FDRStrip fdrs={selP.fdrs} size={9}/></div>
                </div>
                <div style={{fontSize:9,color:MU,marginBottom:6}}>{cands.length} candidates · budget £{(bank+selP.sellPrice).toFixed(1)}m</div>
                {cands.map(c=>(
                  <div key={c.id} onClick={()=>doReplace(selId,c.id)} onMouseEnter={e=>e.currentTarget.style.background=C3} onMouseLeave={e=>e.currentTarget.style.background=C2}
                    style={{...c2s({padding:"7px 10px",marginBottom:4,borderLeft:`3px solid ${c.gain>0?GR:RD}`,cursor:"pointer",transition:"background 0.1s"})}}>
                    <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                      <div><span style={{fontWeight:700,fontSize:12,color:TX}}>{c.name}</span><span style={{fontSize:9,color:MU,marginLeft:4}}>{c.team}</span></div>
                      <div style={{display:"flex",gap:5,alignItems:"center"}}><span style={{fontSize:12,color:c.gain>0?GR:RD,...mn,fontWeight:800}}>{c.gain>0?"+":""}{c.gain}</span><Btn small variant="green"><Check size={9}/></Btn></div>
                    </div>
                    <div style={{display:"flex",justifyContent:"space-between",marginTop:3}}><FDRStrip fdrs={c.fdrs} size={8}/><div style={{display:"flex",gap:6}}><span style={{fontSize:9,color:AM,...mn}}>£{n1(c.price)}m</span><span style={{fontSize:9,color:MU,...mn}}>{n1(c.pts5GW)}</span></div></div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div style={cs({padding:"12px 14px"})}>
            <div style={{fontSize:10,color:MU,marginBottom:6}}>5GW squad projection</div>
            <ResponsiveContainer width="100%" height={108}>
              <BarChart data={gwP} margin={{top:2,right:2,bottom:0,left:-20}}>
                <CartesianGrid strokeDasharray="3 3" stroke={BD} vertical={false}/><XAxis dataKey="gw" tick={{fontSize:9,fill:MU}}/><YAxis tick={{fontSize:9,fill:MU}}/><Tooltip content={<CT/>}/>
                <Bar dataKey="pts" fill={ACT} radius={[3,3,0,0]} name="Proj pts"/>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════════════════
   TEAM BUILDER — 3-step wizard + model weights
════════════════════════════════════════════════════════ */
const STRATS=[
  {id:"attack",   icon:"⚡",title:"Attack First",       desc:"Maximize goals and assists. High-scoring forwards and midfielders."},
  {id:"balanced", icon:"⚖️",title:"Balanced",           desc:"Mix of attacking returns and defensive solidity."},
  {id:"defensive",icon:"🛡️",title:"Defensive Wall",     desc:"Lock down clean sheets. Strong defense and goalkeepers."},
  {id:"diff",     icon:"🎯",title:"Differential Hunter",desc:"Find hidden gems with low ownership."},
]
const HORIZONS=[
  {id:"short", icon:"⚡",title:"Next 1–2 GWs",desc:"Focus on immediate fixtures and current form."},
  {id:"medium",icon:"📅",title:"Next 3–5 GWs",desc:"Balance current form with upcoming fixtures."},
  {id:"long",  icon:"📊",title:"Season-Long",  desc:"Focus on underlying stats and consistency."},
]
const RISKS=[
  {id:"safe",icon:"🛡️",title:"Play It Safe",        desc:"Reliable starters with consistent minutes."},
  {id:"mid", icon:"⚖️",title:"Balanced Risk",        desc:"Mix of safe picks and upside potential."},
  {id:"high",icon:"🎲",title:"High Risk / High Reward",desc:"Chasing upside even if rotation is a concern."},
]
const STRAT_W={
  attack:   {rel:30,fix:65,xgPts:85,ict:70,bps:50,bpb:60,form:70,cs:20,dc:20,xgc:15},
  balanced: {rel:55,fix:55,xgPts:60,ict:55,bps:55,bpb:55,form:60,cs:45,dc:45,xgc:40},
  defensive:{rel:70,fix:50,xgPts:30,ict:40,bps:60,bpb:65,form:50,cs:80,dc:80,xgc:75},
  diff:     {rel:40,fix:70,xgPts:65,ict:60,bps:45,bpb:50,form:55,cs:40,dc:35,xgc:35},
}
function WCard({item,sel,onSel}){
  return(
    <div onClick={onSel} style={{...c2s({padding:"16px",cursor:"pointer",borderColor:sel?ACT:BD,background:sel?ACT+"10":C2,transition:"all 0.12s"})}}>
      <div style={{fontSize:22,marginBottom:8}}>{item.icon}</div>
      <div style={{fontWeight:700,fontSize:13,color:sel?ACT:TX,marginBottom:5}}>{item.title}</div>
      <div style={{fontSize:11,color:MU,lineHeight:1.55}}>{item.desc}</div>
      {sel&&<div style={{marginTop:8,fontSize:9,color:ACT,fontWeight:700}}>✓ SELECTED</div>}
    </div>
  )
}
function TeamBuilderPage(){
  const [step,setStep]=useState(1)
  const [strat,setStrat]=useState(null)
  const [horiz,setHoriz]=useState(null)
  const [risk,setRisk]=useState(null)
  const [ownMin,setOMin]=useState(0),[ownMax,setOMax]=useState(80)
  const [win,setWin]=useState(5),[fix,setFix]=useState(5)
  const [W,setWts]=useState({rel:55,fix:55,xgPts:60,ict:55,bps:55,bpb:55,form:60,cs:45,dc:45,xgc:40})
  const sw=k=>v=>setWts(w=>({...w,[k]:v}))
  const applySt=id=>{setStrat(id);setWts(STRAT_W[id]||W)}

  const scored=useMemo(()=>{
    if(!strat)return[]
    const hm=horiz==="short"?1.18:horiz==="long"?0.88:1.0
    const rf=risk==="safe"
      ? p=>p.minRel>=0.86
      : risk==="high"
        ? p=>p.minRel>=0.55
        : p=>p.minRel>=0.70

    return PLAYERS
      .filter(p=>rf(p)&&p.own>=ownMin&&p.own<=ownMax)
      .map(p=>{
        const lookahead=Math.max(1,Math.round(fix))
        const fdrSlice=p.fdrs.slice(0,lookahead)
        const fdrAvg=fdrSlice.length?fdrSlice.reduce((s,v)=>s+v,0)/fdrSlice.length:3
        const fixtureEase=Math.max(0,Math.min(100,(6-fdrAvg)*20))

        const formWindow=Math.max(2,Math.round(win))
        const sample=p.history.slice(-formWindow)
        const rollingForm=sample.length?sample.reduce((s,v)=>s+v,0)/sample.length:p.form

        const attackCore=Math.min(100,((p.xg90*100)+(p.xa90*100)+(p.xgi90*80)+(p.pts90*10))/4)
        const ictNorm=Math.min(100,(p.ict/80)*100)
        const bpsNorm=Math.min(100,(p.bps/60)*100)
        const bonusNorm=Math.min(100,p.bonusProb*100)
        const formNorm=Math.min(100,rollingForm*10)
        const csNorm=Math.min(100,p.csRate*100)
        const dcNorm=Math.min(100,p.dcP90*20)
        const xgcNorm=Math.max(0,100-p.xgc90*25)
        const reliability=Math.min(100,p.minRel*100)

        let strategyBoost=0
        if(strat==="attack"&&(p.pos==="MID"||p.pos==="FWD"))strategyBoost=6
        if(strat==="defensive"&&(p.pos==="GK"||p.pos==="DEF"))strategyBoost=8
        if(strat==="balanced")strategyBoost=4
        if(strat==="diff")strategyBoost=Math.max(0,(25-p.own)/4)

        const totalWeight=W.rel+W.fix+W.xgPts+W.ict+W.bps+W.bpb+W.form+W.cs+W.dc+W.xgc
        const raw=(
          reliability*W.rel+
          fixtureEase*W.fix+
          attackCore*W.xgPts+
          ictNorm*W.ict+
          bpsNorm*W.bps+
          bonusNorm*W.bpb+
          formNorm*W.form+
          csNorm*W.cs+
          dcNorm*W.dc+
          xgcNorm*W.xgc
        )/Math.max(totalWeight,1)

        return{
          ...p,
          modelScore:+((raw*hm)+strategyBoost).toFixed(2),
          fixtureEase:+fixtureEase.toFixed(1),
          rollingForm:+rollingForm.toFixed(2),
          points90:+p.pts90.toFixed(2),
        }
      })
      .sort((a,b)=>b.modelScore-a.modelScore)
  },[strat,horiz,risk,ownMin,ownMax,win,fix,W])

  const byPos=useMemo(()=>({
    GK:scored.filter(p=>p.pos==="GK"),
    DEF:scored.filter(p=>p.pos==="DEF"),
    MID:scored.filter(p=>p.pos==="MID"),
    FWD:scored.filter(p=>p.pos==="FWD"),
  }),[scored])

  const formation=strat==="defensive"?"5-4-1":(strat==="attack"||strat==="diff")?"3-4-3":"3-5-2"

  const xi=useMemo(()=>{
    const[nD,nM,nF]=FORMATIONS[formation]
    const gk=byPos.GK.slice(0,1)
    const defs=byPos.DEF.slice(0,nD)
    const mids=byPos.MID.slice(0,nM)
    const fwds=byPos.FWD.slice(0,nF)
    const starters=[...gk,...defs,...mids,...fwds]
    const used=new Set(starters.map(p=>p.id))
    const bench=scored.filter(p=>!used.has(p.id)).slice(0,4)
    const proj=starters.reduce((s,p)=>s+p.nextGW,0)
    const cost=starters.reduce((s,p)=>s+p.price,0)
    return{gk,defs,mids,fwds,bench,proj:+proj.toFixed(1),cost:+cost.toFixed(1)}
  },[byPos,formation,scored])

  const ready=Boolean(strat&&horiz&&risk)
  const canContinue=step===1?Boolean(strat):step===2?Boolean(horiz):Boolean(risk)
  const cfg=step===1
    ? {q:"What's your FPL strategy?",desc:"Choose the approach that matches your playing style.",opts:STRATS,sel:strat,onSel:applySt}
    : step===2
      ? {q:"What's your time horizon?",desc:"How far ahead are you planning?",opts:HORIZONS,sel:horiz,onSel:setHoriz}
      : {q:"What's your risk tolerance?",desc:"How adventurous do you want to be?",opts:RISKS,sel:risk,onSel:setRisk}

  const topRows=scored.slice(0,24)

  return(
    <div style={{padding:"16px 20px",maxWidth:1300,margin:"0 auto"}}>
      <div style={{display:"grid",gridTemplateColumns:"1.1fr 0.9fr",gap:14,alignItems:"start"}}>
        <div style={{display:"flex",flexDirection:"column",gap:12}}>
          <div style={cs({padding:"14px 16px"})}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",gap:10,marginBottom:8}}>
              <div>
                <div style={{fontSize:18,fontWeight:800,color:TX}}>Guided Strategy Builder</div>
                <div style={{fontSize:11,color:MU}}>Answer 3 quick questions and we'll set optimal weights for your strategy.</div>
              </div>
              <Tag label={`Step ${step}/3`} color={ACT}/>
            </div>

            <div style={{display:"flex",gap:6,marginBottom:10}}>
              {[1,2,3].map(n=><div key={n} style={{height:4,flex:1,borderRadius:3,background:n<=step?ACT:BD}}/>) }
            </div>

            <div style={{marginBottom:8}}>
              <div style={{fontSize:14,fontWeight:700,color:TX,marginBottom:3}}>{cfg.q}</div>
              <div style={{fontSize:11,color:MU}}>{cfg.desc}</div>
            </div>

            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(190px,1fr))",gap:10}}>
              {cfg.opts.map(item=><WCard key={item.id} item={item} sel={cfg.sel===item.id} onSel={()=>cfg.onSel(item.id)}/>) }
            </div>

            <div style={{display:"flex",justifyContent:"space-between",marginTop:12}}>
              <Btn small variant="ghost" onClick={()=>setStep(s=>Math.max(1,s-1))} disabled={step===1}><ArrowLeft size={11}/> Back</Btn>
              <Btn small variant={step===3?"green":"primary"} onClick={()=>setStep(s=>Math.min(3,s+1))} disabled={!canContinue}>{step===3?"Strategy Locked":"Next"}</Btn>
            </div>
          </div>

          <div style={cs({padding:"14px 16px"})}>
            <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:6}}>
              <Sliders size={13} style={{color:ACT}}/>
              <span style={{fontSize:13,fontWeight:700,color:TX}}>Model Weights</span>
            </div>
            <div style={{fontSize:10,color:MU,marginBottom:12}}>Tune how the model scores players using reliability, fixtures and core FPL stats.</div>

            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:10}}>
              <SliderRow label="Reliability" val={W.rel} setVal={sw("rel")} desc="Rotation risk - higher weight = avoid bench-prone players."/>
              <SliderRow label="Upcoming Fixture Difficulty" val={W.fix} setVal={sw("fix")} desc="Easier fixtures = higher score."/>
              <SliderRow label="FPL Stats (xG, xA, points per 90)" val={W.xgPts} setVal={sw("xgPts")}/>
              <SliderRow label="ICT Index" val={W.ict} setVal={sw("ict")} desc="Influence, Creativity, Threat."/>
              <SliderRow label="BPS" val={W.bps} setVal={sw("bps")}/>
              <SliderRow label="Bonus Probability" val={W.bpb} setVal={sw("bpb")}/>
              <SliderRow label="Form" val={W.form} setVal={sw("form")}/>
              <SliderRow label="Clean Sheet Rate" val={W.cs} setVal={sw("cs")}/>
              <SliderRow label="Defensive Contributions per 90" val={W.dc} setVal={sw("dc")}/>
              <SliderRow label="xGC per 90" val={W.xgc} setVal={sw("xgc")}/>
            </div>

            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:10,marginTop:4}}>
              <SliderRow label="Stats Window" val={win} setVal={setWin} min={2} max={10} step={1} color={AM} desc="Average player stats over the last N gameweeks. Smooths out one-week outliers to show consistent performance."/>
              <SliderRow label="Fixture Lookahead" val={fix} setVal={setFix} min={2} max={8} step={1} color={IN} desc="Consider fixture difficulty for the next N gameweeks. Forward-looking metric for upcoming matches."/>
            </div>

            <div style={{marginTop:8,paddingTop:8,borderTop:`1px solid ${BD}`}}>
              <div style={{fontSize:12,fontWeight:600,color:TX,marginBottom:2}}>Ownership Range</div>
              <div style={{fontSize:10,color:MU,marginBottom:8}}>Filter player pool by ownership to push safety or differentials.</div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:10}}>
                <div>
                  <div style={{display:"flex",justifyContent:"space-between",marginBottom:2}}><span style={{fontSize:10,color:MU}}>Min Ownership</span><span style={{fontSize:10,color:TX,...mn}}>{ownMin}%</span></div>
                  <input type="range" min={0} max={95} step={1} value={ownMin} onChange={e=>setOMin(Math.min(+e.target.value,ownMax-1))} style={{width:"100%",accentColor:ACT}}/>
                </div>
                <div>
                  <div style={{display:"flex",justifyContent:"space-between",marginBottom:2}}><span style={{fontSize:10,color:MU}}>Max Ownership</span><span style={{fontSize:10,color:TX,...mn}}>{ownMax}%</span></div>
                  <input type="range" min={5} max={100} step={1} value={ownMax} onChange={e=>setOMax(Math.max(+e.target.value,ownMin+1))} style={{width:"100%",accentColor:GR}}/>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div style={{display:"flex",flexDirection:"column",gap:12}}>
          <div style={cs({padding:"14px 16px"})}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:8,marginBottom:8}}>
              <div>
                <div style={{fontSize:13,fontWeight:700,color:TX}}>Model Output</div>
                <div style={{fontSize:10,color:MU}}>{ready?`Formation ${formation} · ${scored.length} players scored`:"Complete all 3 strategy questions to generate picks."}</div>
              </div>
              <Tag label={ready?"Ready":"Waiting"} color={ready?GR:AM}/>
            </div>

            {ready?(
              <>
                <div style={{display:"grid",gridTemplateColumns:"repeat(3,minmax(0,1fr))",gap:8,marginBottom:10}}>
                  {[ ["Formation",formation,ACT],["Next GW",`${n1(xi.proj)} pts`,GR],["XI Cost",`£${n1(xi.cost)}m`,AM] ].map(([l,v,c])=>(
                    <div key={l} style={{...c2s({padding:"7px 9px"})}}>
                      <div style={{fontSize:9,color:MU,textTransform:"uppercase",letterSpacing:"0.08em"}}>{l}</div>
                      <div style={{fontSize:14,fontWeight:800,color:c,...mn}}>{v}</div>
                    </div>
                  ))}
                </div>

                <div style={{fontSize:11,color:MU,marginBottom:6}}>Suggested XI</div>
                {[ ["GK",xi.gk,AM],["DEF",xi.defs,"#60a5fa"],["MID",xi.mids,"#34d399"],["FWD",xi.fwds,"#f87171"],["Bench",xi.bench,MU2] ].map(([lbl,arr,col])=>(
                  <div key={lbl} style={{display:"flex",gap:8,padding:"4px 0",alignItems:"flex-start",borderBottom:`1px solid ${BD}22`}}>
                    <span style={{minWidth:44,fontSize:10,color:col,fontWeight:700}}>{lbl}</span>
                    <div style={{display:"flex",gap:5,flexWrap:"wrap",flex:1}}>
                      {arr.map(p=><span key={p.id} style={{background:C2,border:`1px solid ${BD}`,borderRadius:4,padding:"2px 6px",fontSize:10,color:TX}}>{p.name} · {n1(p.modelScore)}</span>)}
                    </div>
                  </div>
                ))}
              </>
            ):(
              <div style={{fontSize:12,color:MU,padding:"10px 0"}}>Set your strategy, horizon, and risk profile to unlock team suggestions.</div>
            )}
          </div>

          <div style={cs({padding:"10px 0 0"})}>
            <div style={{padding:"0 12px 10px",display:"flex",justifyContent:"space-between",alignItems:"center",gap:8}}>
              <div style={{fontSize:12,fontWeight:700,color:TX}}>Top Model Candidates</div>
              <div style={{fontSize:10,color:MU}}>Includes xG/xA, points per 90, ICT, BPS, bonus probability, form, CS rate, DC/90, xGC/90</div>
            </div>
            <div style={{padding:"0 10px 10px",maxHeight:340,overflowY:"auto",overflowX:"auto"}}>
              <table style={{width:"100%",borderCollapse:"collapse"}}>
                <thead>
                  <tr>
                    <th style={TH}>#</th>
                    <th style={TH}>Player</th>
                    <th style={TH}>Pos</th>
                    <th style={{...TH,minWidth:120}}>Next Fixtures</th>
                    <th style={{...TH,textAlign:"right"}}>Price</th>
                    <th style={{...TH,textAlign:"right"}}>Ownership</th>
                    <th style={{...TH,textAlign:"right"}}>Minutes</th>
                    <th style={{...TH,textAlign:"right"}}>Points</th>
                    <th style={{...TH,textAlign:"right"}}>Points/90</th>
                    <th style={{...TH,textAlign:"right"}}>xG/90</th>
                    <th style={{...TH,textAlign:"right"}}>xA/90</th>
                    <th style={{...TH,textAlign:"right"}}>GI/90</th>
                    <th style={{...TH,textAlign:"right"}}>ICT</th>
                    <th style={{...TH,textAlign:"right"}}>BPS</th>
                    <th style={{...TH,textAlign:"right"}}>Bonus Prob</th>
                    <th style={{...TH,textAlign:"right"}}>Form</th>
                    <th style={{...TH,textAlign:"right"}}>CS Rate</th>
                    <th style={{...TH,textAlign:"right"}}>DC/90</th>
                    <th style={{...TH,textAlign:"right"}}>xGC/90</th>
                    <th style={{...TH,textAlign:"right"}}>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {topRows.map((p,i)=>(
                    <tr key={p.id}>
                      <td style={{...TD,color:MU,...mn}}>{i+1}</td>
                      <td style={{...TD,fontWeight:700}}>{p.name}</td>
                      <td style={TD}><span style={ptag(p.pos)}>{p.pos}</span></td>
                      <td style={TD}>
                        <div style={{display:"flex",gap:3}}>
                          {p.fdrs.slice(0,3).map((f,fi)=><span key={fi} style={{...fdp(f),fontSize:8,padding:"1px 4px"}}>{p.opps[fi]?.split(" ")[0]||"BGW"}</span>)}
                        </div>
                      </td>
                      <td style={{...TD,textAlign:"right",...mn,color:AM}}>£{n1(p.price)}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{n1(p.own)}%</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{ni(p.mins)}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{ni(p.points)}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{n2(p.points90)}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{n2(p.xg90)}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{n2(p.xa90)}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{n2(p.gi90)}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{n1(p.ict)}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{ni(p.bps)}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{`${Math.round(p.bonusProb*100)}%`}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{n1(p.rollingForm)}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{`${Math.round(p.csRate*100)}%`}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{n2(p.dcP90)}</td>
                      <td style={{...TD,textAlign:"right",...mn}}>{n2(p.xgc90)}</td>
                      <td style={{...TD,textAlign:"right",...mn,fontWeight:800,color:GR}}>{n1(p.modelScore)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

const PAGES=[
  {id:"results",label:"Gameweek Results",icon:Activity},
  {id:"analytics",label:"Player Analytics",icon:BarChart2},
  {id:"fixtures",label:"Fixtures",icon:Shield},
  {id:"compare",label:"Compare",icon:Users},
  {id:"planner",label:"Transfer Planner",icon:RefreshCw},
  {id:"builder",label:"Team Builder",icon:Sliders},
]

export default function FPLDashboard(){
  const [page,setPage]=useState("results")
  const [compareList,setCompareList]=useState([1,2])
  const [shortlist,setShortlist]=useState([1,4,8])
  const [squad,setSquad]=useState(DEFAULT_SQUAD)
  const [bench,setBench]=useState(DEFAULT_BENCH)
  const [captain,setCaptain]=useState(1)
  const [vc,setVc]=useState(4)
  const [bank,setBank]=useState(1.5)
  const [ft,setFt]=useState(2)
  const [chip,setChip]=useState(null)

  const { data: predictionData } = usePredictions(undefined, undefined, false, "pts_next5", {
    season: "2526",
    limit: 250,
    include_breakdown: true,
    include_stats: true,
  })
  const { data: tickerData } = useFixtureTicker(5)
  const { data: teamsData } = useTeams()
  const { data: liveMatchesData } = useLiveMatches()
  const { data: livePointsData } = useLivePoints()
  const { data: finishedFixturesData } = useFixtures({ season: "2526", finished: true })

  const teamMap=useMemo(()=>{
    const m={}
    ;(teamsData?.teams||[]).forEach(t=>{m[t.code]=t})
    ;(tickerData?.ticker||[]).forEach(t=>{
      if(!m[t.team_code])m[t.team_code]={code:t.team_code,short_name:t.short_name,name:t.name}
    })
    return m
  },[teamsData,tickerData])

  const tickerByTeam=useMemo(()=>{
    const m={}
    ;(tickerData?.ticker||[]).forEach(t=>{m[t.team_code]=t.fixtures||[]})
    return m
  },[tickerData])

  const analyticsRows=useMemo(()=>{
    const preds=predictionData?.predictions||[]
    if(!preds.length)return PLAYERS

    return preds.map(p=>{
      const fb=PLmap[p.player_id]
      const stat=p.latest_stat||{}
      const rolling=stat.rolling||{}

      const minutes=toNum(stat.minutes, toNum(fb?.mins, 0))
      const goals=toNum(stat.goals, toNum(fb?.goals, 0))
      const assists=toNum(stat.assists, toNum(fb?.assists, 0))
      const gi=goals+assists
      const goals90=minutes>0?+(goals*90/minutes).toFixed(2):toNum(fb?.goals90,0)
      const assists90=minutes>0?+(assists*90/minutes).toFixed(2):toNum(fb?.assists90,0)
      const gi90=minutes>0?+(gi*90/minutes).toFixed(2):toNum(fb?.gi90,0)

      const chance=chancePct(p.chance_of_playing)
      const isAvail=!p.is_unavailable&&chance>=75
      const price=toNum(p.price_m,toNum(fb?.price,0))
      const pts5GW=toNum(p.pts_next5,toNum(fb?.pts5GW,0))
      const nextGW=toNum(p.predicted_pts,toNum(fb?.nextGW,0))

      const infl=pickNum(rolling,["gw_influence","influence","r3_gw_influence","r5_gw_influence"],toNum(fb?.infl,0))
      const cre=pickNum(rolling,["gw_creativity","creativity","r3_gw_creativity","r5_gw_creativity"],toNum(fb?.cre,0))
      const thr=pickNum(rolling,["gw_threat","threat","r3_gw_threat","r5_gw_threat"],toNum(fb?.thr,0))
      const ict=pickNum(rolling,["gw_ict_index","ict_index","r3_gw_ict_index","r5_gw_ict_index"],toNum(fb?.ict, infl+cre+thr))

      const dc=pickNum(rolling,["gw_defensive_contribution","defensive_contribution","r3_gw_defensive_contribution","r5_gw_defensive_contribution"],toNum(fb?.dc,0))
      const dcP90=pickNum(rolling,["defensive_contribution_per_90","gw_defensive_contribution_per_90","r3_gw_defensive_contribution_per_90"],minutes>0?dc*90/minutes:toNum(fb?.dcP90,0))
      const cbi=pickNum(rolling,["gw_clearances_blocks_interceptions","clearances_blocks_interceptions","r3_gw_clearances_blocks_interceptions"],toNum(fb?.cbi,0))
      const tackles=pickNum(rolling,["gw_tackles","tackles","r3_gw_tackles"],toNum(fb?.tackles,0))
      const rec=pickNum(rolling,["gw_recoveries","recoveries","r3_gw_recoveries"],toNum(fb?.rec,0))
      const cs=toNum(stat.clean_sheets,toNum(fb?.cs,0))
      const gc=toNum(stat.goals_conceded,toNum(fb?.gc,0))
      const xg=toNum(stat.xg,toNum(fb?.xg,0))
      const xa=toNum(stat.xa,toNum(fb?.xa,0))
      const xgi=toNum(stat.xgi,toNum(fb?.xgi,xg+xa))
      const xg90=toNum(stat.xg_per90,toNum(fb?.xg90,0))
      const xa90=toNum(stat.xa_per90,toNum(fb?.xa90,0))
      const xgi90=toNum(stat.xgi_per90,toNum(fb?.xgi90,0))
      const xgc=toNum(stat.xgc,toNum(fb?.xgc,0))
      const xgc90=toNum(stat.xgc_per90,toNum(fb?.xgc90,0))

      const teamFixtures=tickerByTeam[p.team_code]||[]
      const bd=Object.entries(p.gw_breakdown||{}).sort((a,b)=>Number(a[0])-Number(b[0])).slice(0,5)
      const fdrs=bd.length
        ? bd.map(([,v])=>toNum(v?.fdr,3))
        : teamFixtures.slice(0,5).map(f=>toNum(f?.fdr,3))
      const afdr=bd.length
        ? bd.map(([,v])=>toNum(v?.attack_fdr,toNum(v?.fdr,3)))
        : teamFixtures.slice(0,5).map(f=>toNum(f?.attack_fdr,toNum(f?.fdr,3)))
      const dfdr=bd.length
        ? bd.map(([,v])=>toNum(v?.defence_fdr,toNum(v?.fdr,3)))
        : teamFixtures.slice(0,5).map(f=>toNum(f?.defence_fdr,toNum(f?.fdr,3)))
      const opps=bd.length
        ? bd.map(([,v])=>String(v?.opp||"BGW"))
        : teamFixtures.slice(0,5).map(f=>{
            const opp=teamMap[f?.opponent_code]?.short_name||String(f?.opponent_code||"BGW")
            return `${opp}${f?.is_home?" (H)":" (A)"}`
          })
      const gwPreds=bd.length
        ? bd.map(([,v])=>toNum(v?.pred,0))
        : GW_NEXT.map((_,i)=>+(nextGW*(1+(3-(fdrs[i]||3))*0.08)).toFixed(1))

      const history=fb?.history||gp(Math.max(2,nextGW),p.player_id*17)
      const form=pickNum(rolling,["form","r3_gw_event_points"],toNum(fb?.form,toNum(stat.pts,nextGW)))
      const points=pickNum(rolling,["total_points","r5_gw_total_points"],toNum(fb?.points,pts5GW*4))
      const csRate=pickNum(rolling,["clean_sheets_per_90","gw_clean_sheets_per_90"],minutes>0?(cs*90)/minutes:toNum(fb?.csRate,0))
      const bps=toNum(stat.bps,toNum(fb?.bps,0))
      const bonusProb=clamp(toNum(fb?.bonusProb,bps/100),0,1)

      const shortTeam=teamMap[p.team_code]?.short_name||fb?.team||String(p.team_code)

      return{
        id:p.player_id,
        name:p.web_name,
        team:shortTeam,
        pos:p.position,
        price,
        own:toNum(p.selected_by_pct,toNum(fb?.own,0)),
        form,
        xgi90,
        xg90,
        xa90,
        nextGW,
        pts5GW,
        points,
        chance,
        mins:minutes,
        goals,
        assists,
        gi,
        xg,
        xa,
        xgi,
        cs,
        gc,
        xgc,
        xgc90,
        dc,
        dcP90,
        dch:Math.max(0,Math.round(dc*0.4)),
        tackles,
        cbi,
        rec,
        infl,
        cre,
        thr,
        ict,
        bps,
        bonusProb,
        csRate,
        og:toNum(stat.own_goals,toNum(fb?.og,0)),
        ps:toNum(stat.penalties_saved,toNum(fb?.ps,0)),
        pm:toNum(stat.penalties_missed,toNum(fb?.pm,0)),
        gi90,
        goals90,
        assists90,
        pts90:minutes>0?+(pts5GW*90/Math.max(minutes,1)).toFixed(2):toNum(fb?.pts90,0),
        fdrs,
        afdr,
        dfdr,
        opps,
        gwPreds,
        history,
        roll5:history.map((_,i,a)=>i<4?null:+(a.slice(i-4,i+1).reduce((s,v)=>s+v,0)/5).toFixed(1)),
        sellPrice:+Math.max(0,price-0.1).toFixed(1),
        valueScore:price>0?+(pts5GW/price).toFixed(2):0,
        isAvail,
        minRel:clamp(minutes/90,0,1),
      }
    })
  },[predictionData,tickerByTeam,teamMap])

  const fixtureRows=useMemo(()=>{
    if(!tickerData?.ticker?.length)return null
    return tickerData.ticker.map(t=>({
      code:t.short_name||teamMap[t.team_code]?.short_name||String(t.team_code),
      fixtures:(t.fixtures||[]).slice(0,5).map(f=>({
        o:teamMap[f.opponent_code]?.short_name||String(f.opponent_code),
        h:f.is_home?1:0,
        f:toNum(f.fdr,3),
        af:toNum(f.attack_fdr,toNum(f.fdr,3)),
        df:toNum(f.defence_fdr,toNum(f.fdr,3)),
      })),
    }))
  },[tickerData,teamMap])

  const gwResultsPayload=useMemo(()=>{
    const fixtures=finishedFixturesData?.fixtures||[]
    if(!fixtures.length)return{gwLabel:"Gameweek 31",matches:GW_RESULTS}

    const latestGw=fixtures.reduce((mx,f)=>Math.max(mx,toNum(f.gw,0)),0)
    const rows=fixtures.filter(f=>toNum(f.gw,0)===latestGw).slice(0,10).map((f,i)=>{
      const home=teamMap[f.team_h_code]?.short_name||String(f.team_h_code)
      const away=teamMap[f.team_a_code]?.short_name||String(f.team_a_code)
      const keyPlayer=(analyticsRows||PLAYERS)
        .filter(p=>p.team===home||p.team===away)
        .sort((a,b)=>b.nextGW-a.nextGW)[0]
      return{
        id:`${latestGw}-${i}`,
        home,
        away,
        hs:toNum(f.team_h_score,0),
        as:toNum(f.team_a_score,0),
        scorers:[],
        assist:[],
        key:keyPlayer&&PLmap[keyPlayer.id]?keyPlayer.id:null,
      }
    })
    return{gwLabel:`Gameweek ${latestGw}`,matches:rows.length?rows:GW_RESULTS}
  },[finishedFixturesData,teamMap,analyticsRows])

  const liveMatches=useMemo(()=>{
    const ms=liveMatchesData?.matches||[]
    if(!ms.length)return LIVE_MATCHES
    return ms.map(m=>({
      id:m.fixture_id,
      home:teamMap[m.team_h_id]?.short_name||String(m.team_h_id),
      away:teamMap[m.team_a_id]?.short_name||String(m.team_a_id),
      hs:m.team_h_score,
      as:m.team_a_score,
      status:m.finished?"FT":m.started?"LIVE":"KO",
      mins:toNum(m.minutes,0),
    }))
  },[liveMatchesData,teamMap])

  const liveStatsById=useMemo(()=>{
    const m={}
    ;(livePointsData?.players||[]).forEach(p=>{m[p.player_id]=p})
    return m
  },[livePointsData])

  const scoredRows=analyticsRows?.length?analyticsRows:PLAYERS
  const topScorers=useMemo(()=>[...scoredRows].sort((a,b)=>{
    const ga=toNum(liveStatsById[a.id]?.goals_scored,a.goals)
    const gb=toNum(liveStatsById[b.id]?.goals_scored,b.goals)
    return gb-ga
  }).slice(0,5),[scoredRows,liveStatsById])
  const topAssists=useMemo(()=>[...scoredRows].sort((a,b)=>{
    const aa=toNum(liveStatsById[a.id]?.assists,a.assists)
    const ab=toNum(liveStatsById[b.id]?.assists,b.assists)
    return ab-aa
  }).slice(0,5),[scoredRows,liveStatsById])

  const onAddCompare=useCallback((id)=>{
    setCompareList(list=>{
      if(list.includes(id))return list.filter(x=>x!==id)
      if(list.length>=4)return[...list.slice(1),id]
      return[...list,id]
    })
  },[])

  return(
    <div style={{background:BG,color:TX,minHeight:"calc(100vh - 110px)",border:`1px solid ${BD}`,borderRadius:10,overflow:"hidden",boxShadow:"0 20px 48px #00000050"}}>
      <div style={{padding:"12px 16px",borderBottom:`1px solid ${BD}`,background:"linear-gradient(90deg,#0c1828 0%,#11233c 100%)"}}>
        <div style={{display:"flex",alignItems:"center",gap:10,flexWrap:"wrap"}}>
          <div>
            <div style={{fontSize:20,fontWeight:900,color:TX}}>FPL Core Dashboard</div>
            <div style={{fontSize:11,color:MU}}>Gameweek results, fixtures, game details, advanced player analytics, compare, transfer planner, and strategy team builder.</div>
          </div>
          <div style={{marginLeft:"auto",display:"flex",gap:6,alignItems:"center",flexWrap:"wrap"}}>
            <Tag label={`Compare ${compareList.length}/4`} color={ACT}/>
            <Tag label={`Shortlist ${shortlist.length}`} color={AM}/>
            <Tag label={`Bank £${n1(bank)}m`} color={GR}/>
            <Tag label={`FT ${ft}`} color={IN}/>
          </div>
        </div>
        <div style={{display:"flex",gap:4,marginTop:10,overflowX:"auto",paddingBottom:2}}>
          {PAGES.map(({id,label,icon:Icon})=><Btn key={id} small variant={page===id?"primary":"ghost"} onClick={()=>setPage(id)}><Icon size={11}/>{label}</Btn>)}
        </div>
      </div>

      {(page==="planner"||page==="builder")&&<PlanBar squad={squad} bench={bench} captain={captain} vc={vc} bank={bank} ft={ft} chip={chip} onChipChange={setChip}/>}

      {page==="results"&&<ResultsPage gwLabel={gwResultsPayload.gwLabel} resultsMatches={gwResultsPayload.matches} liveMatches={liveMatches} liveGwLabel={liveMatchesData?.gw?`GW${liveMatchesData.gw}`:"GW32"} topScorers={topScorers} topAssists={topAssists}/>} 
      {page==="analytics"&&<AnalyticsPage onAddCompare={onAddCompare} compareList={compareList} shortlist={shortlist} setShortlist={setShortlist} playersData={analyticsRows}/>} 
      {page==="fixtures"&&<FixturesPage tickerRows={fixtureRows} analyticsRows={analyticsRows}/>} 
      {page==="compare"&&<ComparePage compareList={compareList} setCompareList={setCompareList}/>}
      {page==="planner"&&<PlannerPage squad={squad} setSquad={setSquad} bench={bench} setBench={setBench} captain={captain} setCaptain={setCaptain} vc={vc} setVc={setVc} bank={bank} setBank={setBank} ft={ft} setFt={setFt} chip={chip} setPage={setPage}/>}
      {page==="builder"&&<TeamBuilderPage/>}
    </div>
  )
}
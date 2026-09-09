import { Version } from '@microsoft/sp-core-library';
import { BaseClientSideWebPart } from '@microsoft/sp-webpart-base';
import { SPHttpClient, SPHttpClientResponse } from '@microsoft/sp-http';

export interface IPackagingNamingWebPartProps {}

type Stage = 'proposal' | 'waiting' | 'voting' | 'results';

interface IProposal {
  Id: number;
  Title: string;
  NormalizedKey?: string;
  ProposerKey?: string;
  ProposerName?: string;
}

interface IVoteItem {
  Id: number;
  Title: string;
  VoterName: string;
  CandidateIds: string;
}

interface IResultRow {
  id: number;
  name: string;
  proposer: string;
  count: number;
  voters: string[];
  rank: number;
}

export default class PackagingNamingWebPart extends BaseClientSideWebPart<IPackagingNamingWebPartProps> {
  private readonly proposalList = 'PKGNaming_Proposals';
  private readonly voteList = 'PKGNaming_Votes';
  private readonly proposalEnd = Date.parse('2026-09-10T00:00:00+09:00');
  private readonly voteStart = Date.parse('2026-09-10T09:00:00+09:00');
  private readonly voteEnd = Date.parse('2026-09-10T12:00:00+09:00');

  private serverOffset = 0;
  private timer: number | undefined;
  private refreshTimer: number | undefined;
  private busy = false;
  private initialized = false;
  private setupError = '';
  private lastStage: Stage | '' = '';
  private proposalDraft = '';
  private selectedVotes = new Set<number>();
  private userKey = '';
  private userName = '';

  public async onInit(): Promise<void> {
    await super.onInit();
    this.userKey = this.context.pageContext.user.loginName || this.context.pageContext.user.email || this.context.pageContext.user.displayName;
    this.userName = this.context.pageContext.user.displayName || this.context.pageContext.user.email || this.userKey;
    await this.syncServerClock();
    try {
      await this.ensureSchema();
      this.initialized = true;
    } catch (e) {
      this.setupError = this.err(e);
    }
  }

  public render(): void {
    this.renderShell();
    this.refresh().catch(() => undefined);
    if (!this.timer) this.timer = window.setInterval(() => this.updateHeader(), 1000);
    if (!this.refreshTimer) {
      this.refreshTimer = window.setInterval(() => {
        if (!this.busy && document.visibilityState !== 'hidden') this.refresh().catch(() => undefined);
      }, 5000);
    }
  }

  protected onDispose(): void {
    if (this.timer) window.clearInterval(this.timer);
    if (this.refreshTimer) window.clearInterval(this.refreshTimer);
  }

  protected get dataVersion(): Version { return Version.parse('1.0'); }
  private now(): number { return Date.now() + this.serverOffset; }

  private stage(): Stage {
    const n = this.now();
    if (n < this.proposalEnd) return 'proposal';
    if (n < this.voteStart) return 'waiting';
    if (n < this.voteEnd) return 'voting';
    return 'results';
  }

  private async syncServerClock(): Promise<void> {
    try {
      const r = await this.context.spHttpClient.get(`${this.webUrl}/_api/web?$select=Title`, SPHttpClient.configurations.v1, { headers: { Accept: 'application/json;odata=nometadata' } });
      const h = r.headers.get('Date');
      if (h) {
        const t = Date.parse(h);
        if (Number.isFinite(t)) this.serverOffset = t - Date.now();
      }
    } catch { /* client clock fallback */ }
  }

  private get webUrl(): string { return this.context.pageContext.web.absoluteUrl.replace(/\/$/, ''); }

  private renderShell(): void {
    this.domElement.innerHTML = `
      <style>${this.styles()}</style>
      <div class="pn-wrap">
        <section class="pn-hero">
          <div class="pn-eyebrow">PACKAGING TECHNOLOGY · NAMING EVENT</div>
          <h1>신규 패키징 기술 Naming 공모</h1>
          <div class="pn-desc">셀 유닛을 패키징에 넣으면 <b>자중에 의해 장치가 가동되며, 셀을 잡아주는 기술</b></div>
          <div class="pn-pills">
            <span class="pn-pill" id="pn-stage">준비 중</span>
            <span class="pn-pill" id="pn-time">시간 확인 중</span>
            <span class="pn-pill">${this.esc(this.userName)}님</span>
          </div>
        </section>
        <div id="pn-status"></div>
        <main id="pn-app"><section class="pn-card">공용 데이터를 불러오는 중입니다.</section></main>
      </div>`;
    this.updateHeader();
  }

  private updateHeader(): void {
    const s = this.stage();
    const stageEl = this.domElement.querySelector('#pn-stage');
    const timeEl = this.domElement.querySelector('#pn-time');
    const labels: Record<Stage,string> = { proposal: '이름 제안 진행 중', waiting: '제안 마감 · 투표 대기', voting: '투표 진행 중', results: '투표 종료 · 최종 결과' };
    if (stageEl) stageEl.textContent = labels[s];
    if (timeEl) {
      const target = s === 'proposal' ? this.proposalEnd : s === 'waiting' ? this.voteStart : s === 'voting' ? this.voteEnd : 0;
      const prefix = s === 'proposal' ? '제안 마감까지 ' : s === 'waiting' ? '투표 시작까지 ' : s === 'voting' ? '투표 마감까지 ' : '최종 결과 공개 중';
      timeEl.textContent = target ? prefix + this.remain(target - this.now()) : prefix;
    }
    if (this.lastStage && this.lastStage !== s) this.refresh().catch(() => undefined);
    this.lastStage = s;
  }

  private async refresh(): Promise<void> {
    if (this.busy) return;
    this.captureDraft();
    const app = this.domElement.querySelector('#pn-app') as HTMLElement | null;
    const status = this.domElement.querySelector('#pn-status') as HTMLElement | null;
    if (!app) return;
    if (this.setupError) {
      if (status) status.innerHTML = `<div class="pn-notice pn-bad"><b>초기 설정 실패</b><br>${this.esc(this.setupError)}<br><span class="pn-muted">이 Teams/SharePoint 사이트에서 목록 생성 권한(Edit 이상)이 필요합니다.</span></div>`;
      return;
    }
    if (!this.initialized) return;
    try {
      if (status) status.innerHTML = '';
      const s = this.stage();
      if (s === 'proposal') await this.renderProposal(app);
      else if (s === 'waiting') await this.renderWaiting(app);
      else if (s === 'voting') await this.renderVoting(app);
      else await this.renderResults(app);
      this.bindDynamicEvents();
    } catch (e) {
      app.innerHTML = `<section class="pn-card"><div class="pn-notice pn-bad"><b>데이터를 불러오지 못했습니다.</b><br>${this.esc(this.err(e))}</div></section>`;
    }
  }

  private async renderProposal(app: HTMLElement): Promise<void> {
    const [count, mine] = await Promise.all([this.getProposalCount(), this.getMyProposals()]);
    app.innerHTML = `<section class="pn-card"><div class="pn-kicker">전체 후보 건수</div><div class="pn-big">${count}<span> 건</span></div><div class="pn-muted">모든 참여자가 등록한 후보의 총 건수입니다. 다른 사람의 제안 내용과 제안자는 아직 공개되지 않습니다.</div></section><section class="pn-card"><h2>새 이름 제안</h2><div class="pn-muted">여러 개 제안할 수 있습니다. 같은 이름은 한 번만 등록됩니다.</div><div class="pn-form"><input id="pn-proposal" maxlength="80" placeholder="새 이름 입력" value="${this.escAttr(this.proposalDraft)}"><button class="pn-primary" id="pn-add">이름 등록</button></div></section><section class="pn-card"><h2>내가 제안한 이름</h2>${mine.length ? `<div class="pn-list">${mine.map(p => `<div class="pn-item"><div class="pn-name">${this.esc(p.Title)}</div></div>`).join('')}</div>` : '<div class="pn-muted">아직 제안한 이름이 없습니다.</div>'}</section>`;
  }

  private async renderWaiting(app: HTMLElement): Promise<void> {
    const proposals = await this.getAllProposals(false);
    app.innerHTML = `<section class="pn-card"><h2>이름 제안이 마감되었습니다.</h2><div class="pn-notice pn-info"><b>9월 10일 오전 9시</b>부터 같은 화면에서 투표가 시작됩니다. 1인 최대 3개까지 선택할 수 있습니다.</div><div class="pn-kicker">최종 후보</div><div class="pn-big">${proposals.length}<span> 개</span></div><div class="pn-list">${proposals.map(p => `<div class="pn-item"><div class="pn-name">${this.esc(p.Title)}</div></div>`).join('')}</div></section>`;
  }

  private async renderVoting(app: HTMLElement): Promise<void> {
    const [proposals, myVotes] = await Promise.all([this.getAllProposals(false), this.getMyVote()]);
    this.selectedVotes = new Set(myVotes);
    app.innerHTML = `<section class="pn-card"><h2>마음에 드는 이름을 선택해 주세요.</h2><div class="pn-muted">최대 3개까지 선택할 수 있습니다. 투표 중에는 제안자·투표자·득표수가 공개되지 않습니다. 마감 전까지 다시 저장해 변경할 수 있습니다.</div><div class="pn-list">${proposals.sort((a,b)=>a.Title.localeCompare(b.Title,'ko')).map(p => `<div class="pn-vote ${this.selectedVotes.has(p.Id) ? 'sel' : ''}" data-vote="${p.Id}"><div class="pn-check">${this.selectedVotes.has(p.Id) ? '✓' : ''}</div><div class="pn-name">${this.esc(p.Title)}</div></div>`).join('')}</div><div class="pn-sticky"><div><b id="pn-selcount">${this.selectedVotes.size}</b> / 3 선택</div><button class="pn-primary" id="pn-savevote">투표 저장</button></div></section>`;
  }

  private async renderResults(app: HTMLElement): Promise<void> {
    const [proposals, votes] = await Promise.all([this.getAllProposals(true), this.getAllVotes()]);
    const rows = this.rank(proposals, votes);
    const top = rows.filter(r => r.rank <= 3);
    app.innerHTML = `<section class="pn-card"><h2>최종 결과</h2><div class="pn-notice pn-ok">투표가 마감되었습니다. 동점은 공동 순위로 표시하며 최종 선정은 팀에서 진행합니다.</div>${rows.length ? `<div class="pn-top">${top.map(r => `<div class="pn-podium"><div class="pn-rank">${rows.filter(x=>x.rank===r.rank).length>1?'공동 ':''}${r.rank}위</div><div class="pn-rname">${this.esc(r.name)}</div><div class="pn-votes">${r.count}<span> 표</span></div><div class="pn-muted"><b>제안자</b> · ${this.esc(r.proposer)}</div></div>`).join('')}</div><div class="pn-sep"></div><h3>전체 순위</h3>${rows.map(r => `<div class="pn-resultrow"><div class="pn-rn">${rows.filter(x=>x.rank===r.rank).length>1?'공동 ':''}${r.rank}위</div><div class="pn-name">${this.esc(r.name)}</div><div class="pn-rv">${r.count}표</div><div class="pn-people"><b>제안자:</b> ${this.esc(r.proposer)}<br><b>투표자:</b> ${r.voters.length ? r.voters.map(v=>this.esc(v)).join(', ') : '없음'}</div></div>`).join('')}<button class="pn-secondary" id="pn-copy">Teams 공지용 결과 복사</button>` : '<div class="pn-muted">등록된 후보가 없습니다.</div>'}</section>`;
  }

  private bindDynamicEvents(): void {
    const input = this.domElement.querySelector('#pn-proposal') as HTMLInputElement | null;
    const add = this.domElement.querySelector('#pn-add') as HTMLButtonElement | null;
    if (input) input.addEventListener('input', () => { this.proposalDraft = input.value; });
    if (add && input) {
      add.onclick = async () => {
        const name = this.clean(input.value);
        if (!name) return this.toast('제안할 이름을 입력해 주세요.');
        this.proposalDraft = input.value;
        await this.withBusy(add, '저장 중...', async () => {
          if (await this.proposalExists(name)) throw new Error('이미 등록되었습니다.');
          await this.createProposal(name);
          this.proposalDraft = '';
          this.toast('등록되었습니다.');
        });
        await this.refresh();
      };
      input.onkeydown = (e: KeyboardEvent) => { if (e.key === 'Enter') add.click(); };
    }
    this.domElement.querySelectorAll('[data-vote]').forEach(el => {
      (el as HTMLElement).onclick = () => {
        const id = Number((el as HTMLElement).dataset.vote || 0);
        if (this.selectedVotes.has(id)) this.selectedVotes.delete(id);
        else { if (this.selectedVotes.size >= 3) return this.toast('최대 3개까지 선택할 수 있습니다.'); this.selectedVotes.add(id); }
        this.domElement.querySelectorAll('[data-vote]').forEach(x => { const xid = Number((x as HTMLElement).dataset.vote || 0); x.classList.toggle('sel', this.selectedVotes.has(xid)); const c = x.querySelector('.pn-check'); if (c) c.textContent = this.selectedVotes.has(xid) ? '✓' : ''; });
        const count = this.domElement.querySelector('#pn-selcount'); if (count) count.textContent = String(this.selectedVotes.size);
      };
    });
    const save = this.domElement.querySelector('#pn-savevote') as HTMLButtonElement | null;
    if (save) save.onclick = async () => { await this.withBusy(save, '저장 중...', async () => { await this.saveMyVote([...this.selectedVotes]); this.toast('투표가 저장되었습니다.'); }); await this.refresh(); };
    const copy = this.domElement.querySelector('#pn-copy') as HTMLButtonElement | null;
    if (copy) copy.onclick = async () => {
      const [p, v] = await Promise.all([this.getAllProposals(true), this.getAllVotes()]);
      const rows = this.rank(p,v);
      const lines = ['[신규 패키징 기술 Naming 투표 결과]','',...rows.map(r => `${rows.filter(x=>x.rank===r.rank).length>1?'공동 ':''}${r.rank}위 ${r.name} — ${r.count}표`),'','※ 동점은 공동 순위이며 최종 선정은 팀에서 진행합니다.'];
      try { await navigator.clipboard.writeText(lines.join('\n')); this.toast('결과를 복사했습니다.'); } catch { this.toast('복사가 차단되었습니다.'); }
    };
  }

  private captureDraft(): void { const p = this.domElement.querySelector('#pn-proposal') as HTMLInputElement | null; if (p) this.proposalDraft = p.value; }

  private async withBusy(button: HTMLButtonElement, label: string, fn: () => Promise<void>): Promise<void> {
    if (this.busy) return;
    this.busy = true; const original = button.textContent || ''; button.disabled = true; button.textContent = label;
    try { await fn(); } catch (e) { this.toast(this.err(e)); } finally { this.busy = false; button.disabled = false; button.textContent = original; }
  }

  private async ensureSchema(): Promise<void> {
    await this.ensureList(this.proposalList, 'Naming 공모 후보 저장소');
    await this.ensureField(this.proposalList, 'NormalizedKey', 2, true, true);
    await this.ensureField(this.proposalList, 'ProposerKey', 2, true, false);
    await this.ensureField(this.proposalList, 'ProposerName', 2, true, false);
    await this.ensureList(this.voteList, 'Naming 공모 투표 저장소');
    await this.ensureField(this.voteList, 'VoterName', 2, true, false);
    await this.ensureField(this.voteList, 'CandidateIds', 2, false, false);
    await this.ensureUniqueTitle(this.voteList);
  }

  private async ensureList(title: string, description: string): Promise<void> {
    const url = `${this.webUrl}/_api/web/lists/getbytitle('${this.odata(title)}')?$select=Id`;
    const r = await this.context.spHttpClient.get(url, SPHttpClient.configurations.v1, { headers: { Accept: 'application/json;odata=nometadata' } });
    if (r.ok) return;
    if (r.status !== 404) throw new Error(`${title} 확인 실패 (${r.status})`);
    const create = await this.context.spHttpClient.post(`${this.webUrl}/_api/web/lists`, SPHttpClient.configurations.v1, { headers: { Accept: 'application/json;odata=verbose', 'Content-Type': 'application/json;odata=verbose' }, body: JSON.stringify({ __metadata:{type:'SP.List'}, AllowContentTypes:true, BaseTemplate:100, ContentTypesEnabled:true, Description:description, Title:title, Hidden:true }) });
    if (!create.ok && create.status !== 409) throw new Error(`${title} 생성 실패 (${create.status}) ${await create.text()}`);
  }

  private async ensureField(list: string, name: string, kind: number, required: boolean, unique: boolean): Promise<void> {
    const check = await this.context.spHttpClient.get(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(list)}')/fields/getbyinternalnameortitle('${this.odata(name)}')?$select=Id`, SPHttpClient.configurations.v1, { headers:{Accept:'application/json;odata=nometadata'} });
    if (check.ok) return;
    const r = await this.context.spHttpClient.post(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(list)}')/fields`, SPHttpClient.configurations.v1, { headers:{Accept:'application/json;odata=verbose','Content-Type':'application/json;odata=verbose'}, body:JSON.stringify({__metadata:{type:'SP.Field'},Title:name,StaticName:name,FieldTypeKind:kind,Required:required,EnforceUniqueValues:unique,Indexed:unique}) });
    if (!r.ok && r.status !== 409) throw new Error(`${name} 필드 생성 실패 (${r.status}) ${await r.text()}`);
  }

  private async ensureUniqueTitle(list: string): Promise<void> {
    const url = `${this.webUrl}/_api/web/lists/getbytitle('${this.odata(list)}')/fields/getbyinternalnameortitle('Title')`;
    const r = await this.context.spHttpClient.post(url, SPHttpClient.configurations.v1, { headers:{Accept:'application/json;odata=verbose','Content-Type':'application/json;odata=verbose','IF-MATCH':'*','X-HTTP-Method':'MERGE'}, body:JSON.stringify({__metadata:{type:'SP.FieldText'},Indexed:true,EnforceUniqueValues:true}) });
    if (!r.ok) throw new Error(`투표 중복 방지 설정 실패 (${r.status}) ${await r.text()}`);
  }

  private async getProposalCount(): Promise<number> { const j = await this.getJson(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(this.proposalList)}')?$select=ItemCount`); return Number(j.ItemCount || 0); }
  private async getMyProposals(): Promise<IProposal[]> { const f = encodeURIComponent(`ProposerKey eq '${this.odata(this.userKey)}'`); const j = await this.getJson(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(this.proposalList)}')/items?$select=Id,Title&$filter=${f}&$orderby=Id desc&$top=5000`); return j.value || []; }
  private async getAllProposals(includePeople: boolean): Promise<IProposal[]> { const select = includePeople ? 'Id,Title,ProposerName' : 'Id,Title'; const j = await this.getJson(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(this.proposalList)}')/items?$select=${select}&$orderby=Id asc&$top=5000`); return j.value || []; }
  private async proposalExists(name: string): Promise<boolean> { const k = this.normalize(name); const f = encodeURIComponent(`NormalizedKey eq '${this.odata(k)}'`); const j = await this.getJson(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(this.proposalList)}')/items?$select=Id&$filter=${f}&$top=1`); return (j.value || []).length > 0; }

  private async createProposal(name: string): Promise<void> {
    const type = await this.entityType(this.proposalList);
    const r = await this.context.spHttpClient.post(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(this.proposalList)}')/items`, SPHttpClient.configurations.v1, { headers:{Accept:'application/json;odata=verbose','Content-Type':'application/json;odata=verbose'}, body:JSON.stringify({__metadata:{type},Title:name,NormalizedKey:this.normalize(name),ProposerKey:this.userKey,ProposerName:this.userName}) });
    if (!r.ok) { const text = await r.text(); if (r.status === 400 || r.status === 409 || text.toLowerCase().includes('duplicate')) throw new Error('이미 등록되었습니다.'); throw new Error(`등록 실패 (${r.status}) ${text}`); }
  }

  private async getMyVote(): Promise<number[]> { const f = encodeURIComponent(`Title eq '${this.odata(this.userKey)}'`); const j = await this.getJson(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(this.voteList)}')/items?$select=Id,CandidateIds&$filter=${f}&$top=1`); const row = (j.value || [])[0]; if (!row || !row.CandidateIds) return []; return String(row.CandidateIds).split(',').map((x:string)=>Number(x)).filter((x:number)=>Number.isFinite(x) && x>0); }

  private async saveMyVote(ids: number[]): Promise<void> {
    if (ids.length > 3) throw new Error('최대 3개까지 투표할 수 있습니다.');
    if (this.stage() !== 'voting') throw new Error('현재는 투표 시간이 아닙니다.');
    const f = encodeURIComponent(`Title eq '${this.odata(this.userKey)}'`);
    const j = await this.getJson(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(this.voteList)}')/items?$select=Id&$filter=${f}&$top=1`);
    const row = (j.value || [])[0], type = await this.entityType(this.voteList);
    const body = {__metadata:{type},Title:this.userKey,VoterName:this.userName,CandidateIds:ids.join(',')};
    if (row) {
      const r = await this.context.spHttpClient.post(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(this.voteList)}')/items(${row.Id})`, SPHttpClient.configurations.v1, { headers:{Accept:'application/json;odata=verbose','Content-Type':'application/json;odata=verbose','IF-MATCH':'*','X-HTTP-Method':'MERGE'}, body:JSON.stringify(body) });
      if (!r.ok) throw new Error(`투표 저장 실패 (${r.status}) ${await r.text()}`);
    } else {
      const r = await this.context.spHttpClient.post(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(this.voteList)}')/items`, SPHttpClient.configurations.v1, { headers:{Accept:'application/json;odata=verbose','Content-Type':'application/json;odata=verbose'}, body:JSON.stringify(body) });
      if (!r.ok) throw new Error(`투표 저장 실패 (${r.status}) ${await r.text()}`);
    }
  }

  private async getAllVotes(): Promise<IVoteItem[]> { const j = await this.getJson(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(this.voteList)}')/items?$select=Id,Title,VoterName,CandidateIds&$top=5000`); return j.value || []; }

  private rank(proposals: IProposal[], votes: IVoteItem[]): IResultRow[] {
    const map = new Map<number,IResultRow>(); proposals.forEach(p => map.set(p.Id,{id:p.Id,name:p.Title,proposer:p.ProposerName||'확인 불가',count:0,voters:[],rank:0}));
    votes.forEach(v => String(v.CandidateIds||'').split(',').map(x=>Number(x)).filter(x=>Number.isFinite(x)).forEach(id=>{ const r=map.get(id); if(r){r.count++;r.voters.push(v.VoterName||v.Title);} }));
    const rows=[...map.values()].sort((a,b)=>b.count-a.count||a.name.localeCompare(b.name,'ko')); let prev:number|undefined, rank=0;
    rows.forEach((r,i)=>{if(prev===undefined||r.count!==prev)rank=i+1;r.rank=rank;r.voters.sort((a,b)=>a.localeCompare(b,'ko'));prev=r.count;}); return rows;
  }

  private async entityType(list: string): Promise<string> { const j = await this.getJson(`${this.webUrl}/_api/web/lists/getbytitle('${this.odata(list)}')?$select=ListItemEntityTypeFullName`); return j.ListItemEntityTypeFullName; }
  private async getJson(url: string): Promise<any> { const r: SPHttpClientResponse = await this.context.spHttpClient.get(url, SPHttpClient.configurations.v1, {headers:{Accept:'application/json;odata=nometadata'}}); if (!r.ok) throw new Error(`SharePoint 요청 실패 (${r.status}) ${await r.text()}`); return r.json(); }
  private normalize(s:string):string { return this.clean(s).toLocaleLowerCase('ko-KR'); }
  private clean(s:string):string { return String(s||'').trim().replace(/\s+/g,' '); }
  private odata(s:string):string { return String(s||'').replace(/'/g,"''"); }
  private err(e:unknown):string { return e instanceof Error ? e.message : String(e); }
  private esc(s:unknown):string { return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c] || c)); }
  private escAttr(s:unknown):string { return this.esc(s); }
  private remain(ms:number):string { const sec=Math.max(0,Math.floor(ms/1000)),h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60),s=sec%60;return [h,m,s].map(x=>String(x).padStart(2,'0')).join(':'); }
  private toast(message:string):void { let t=this.domElement.querySelector('#pn-toast') as HTMLElement|null;if(!t){t=document.createElement('div');t.id='pn-toast';t.className='pn-toast';this.domElement.appendChild(t);}t.textContent=message;t.classList.add('show');window.setTimeout(()=>t?.classList.remove('show'),2400); }

  private styles(): string { return `.pn-wrap{max-width:980px;margin:0 auto;padding:14px 10px 56px;color:#17202a;font-family:Segoe UI,Noto Sans KR,Malgun Gothic,sans-serif}.pn-hero{background:linear-gradient(135deg,#173d76,#245ca8);color:#fff;border-radius:20px;padding:26px;box-shadow:0 8px 28px rgba(24,39,58,.08)}.pn-eyebrow{font-size:12px;font-weight:800;letter-spacing:.06em;opacity:.82}.pn-hero h1{font-size:clamp(26px,4vw,40px);line-height:1.15;margin:8px 0 12px}.pn-desc{font-size:16px;line-height:1.65;opacity:.95}.pn-pills{display:flex;gap:8px;flex-wrap:wrap;margin-top:17px}.pn-pill{background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.18);border-radius:999px;padding:8px 11px;font-size:13px;font-weight:750}.pn-card{background:#fff;border:1px solid #dfe5ea;border-radius:17px;padding:19px;margin-top:14px;box-shadow:0 8px 28px rgba(24,39,58,.06)}.pn-card h2{font-size:20px;margin:0 0 7px}.pn-card h3{font-size:16px}.pn-muted{color:#68727d;font-size:13px;line-height:1.6}.pn-kicker{font-size:12px;font-weight:800;color:#68727d}.pn-big{font-size:38px;font-weight:950;letter-spacing:-.03em}.pn-big span,.pn-votes span{font-size:14px;font-weight:700;color:#68727d}.pn-form{display:grid;grid-template-columns:1fr auto;gap:9px;margin-top:11px}.pn-form input{width:100%;border:1px solid #cfd7df;border-radius:12px;padding:13px 14px;font-size:16px;outline:none}.pn-form input:focus{border-color:#7ba6ff;box-shadow:0 0 0 3px rgba(37,99,235,.1)}button.pn-primary,button.pn-secondary{border:0;border-radius:12px;padding:12px 15px;font-size:14px;font-weight:800;cursor:pointer}button.pn-primary{background:#2563eb;color:#fff}button.pn-secondary{background:#edf1f5;color:#27313a;margin-top:10px}button:disabled{opacity:.45}.pn-list{display:grid;gap:9px;margin-top:10px}.pn-item,.pn-vote{border:1px solid #dfe5ea;border-radius:14px;padding:13px 14px}.pn-name{font-size:16px;font-weight:850;word-break:break-word}.pn-vote{display:flex;gap:11px;cursor:pointer;align-items:center}.pn-vote.sel{border-color:#78a2f5;background:#f4f8ff}.pn-check{width:24px;height:24px;flex:0 0 24px;border:2px solid #b7c0c9;border-radius:7px;display:grid;place-items:center;color:#fff;font-weight:900}.pn-vote.sel .pn-check{background:#2563eb;border-color:#2563eb}.pn-sticky{position:sticky;bottom:8px;background:rgba(255,255,255,.96);border:1px solid #dfe5ea;border-radius:15px;padding:11px;display:flex;justify-content:space-between;align-items:center;gap:10px;box-shadow:0 8px 25px rgba(0,0,0,.12);margin-top:12px}.pn-notice{border-radius:13px;padding:11px 13px;margin-top:12px;font-size:13px;line-height:1.6}.pn-info{background:#eef5ff;border:1px solid #d5e5ff;color:#234a83}.pn-ok{background:#eefaf4;border:1px solid #cdeedc;color:#12693f}.pn-bad{background:#fff1f1;border:1px solid #ffd2d2;color:#922727}.pn-top{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}.pn-podium{border:1px solid #dfe5ea;border-radius:16px;padding:16px}.pn-rank{font-size:12px;font-weight:900;color:#2563eb}.pn-rname{font-size:19px;font-weight:900;margin:5px 0}.pn-votes{font-size:28px;font-weight:950}.pn-sep{height:1px;background:#dfe5ea;margin:16px 0}.pn-resultrow{display:grid;grid-template-columns:70px 1fr 70px;gap:8px;border-top:1px solid #dfe5ea;padding:13px 0}.pn-rn{font-weight:900}.pn-rv{text-align:right;font-weight:900}.pn-people{grid-column:2/4;color:#68727d;font-size:12px;line-height:1.7}.pn-toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%) translateY(15px);opacity:0;transition:.2s;background:#111827;color:white;padding:11px 14px;border-radius:11px;font-size:13px;font-weight:800;z-index:99999;max-width:90vw;text-align:center}.pn-toast.show{opacity:1;transform:translateX(-50%) translateY(0)}@media(max-width:700px){.pn-top{grid-template-columns:1fr}.pn-form{grid-template-columns:1fr}.pn-form button{width:100%}.pn-hero{padding:22px 18px}.pn-wrap{padding:10px 4px 48px}}`; }
}

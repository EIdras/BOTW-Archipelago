[BOTW_AP_InjectionTest_V208]
moduleMatches = 0x6267BFD0

; ---------------------------------------------------------------------------
; Archipelago -- donner un objet au joueur.
;
; HOOK 1 : 0x031FA97C, per-frame (identifie par l'auteur de FPS++).
;          origine : stw r0, 0x78(r30)       CONFLIT AVEC FPS++
;
; HOOK 2 : 0x02EB5400, dans PauseMenuDataMgr::itemGet, apres le mflr.
;          origine : stw r0, 0x6c(r1)
;          Hooker l'entree (0x02EB53E4) planterait : le bla ecrase LR et le
;          mflr trois instructions plus loin capturerait notre retour.
;
; Le "this" de PauseMenuDataMgr n'est pas cherche statiquement : le hook 2 le
; capture depuis r24 la premiere fois que le joueur ramasse quelque chose.
; Consequence : il faut avoir ramasse un objet une fois par session avant que
; le don fonctionne.
;
; Protocole avec le client Python :
;   1. Python ecrit le nom d'acteur dans apItemName (64 octets)
;   2. Python ecrit la quantite dans apGiveValue
;   3. Python met apGiveReq a 1
;   4. la frame suivante, le cave appelle itemGet et incremente apGiveDone
;
; Registres : r11 et r12 seulement en temps normal. Autour de l'appel a
; itemGet, r0 et r3-r10 sont sauvegardes DANS LE CAVE, pas sur la pile :
; l'assembleur de Cemu ne prend ni mfcr ni stwu a deplacement negatif.
; ---------------------------------------------------------------------------

; itemGet est a 0x02EB53E4 et la vtable SafeString a 0x10263910. Ces deux
; adresses sont chargees en dur avec lis+ori dans le code ci-dessous : voir le
; commentaire sur bctrl pour la raison.
_safeStringVtable = 0x10263910

.origin = codecave

apMagic:
.string "APMBOX01"
.align 4
apVersion:
.int 0x0BADF00E
apTick:
.int 0
apInbox:
.int 0
apOutbox:
.int 0
apLastSeen:
.int 0
apItemGetCount:
.int 0
apLastNamePtr:
.int 0
apLastValue:
.int 0
apPmdmThis:
.int 0
apGiveReq:
.int 0
apGiveValue:
.int 1
apGiveDone:
.int 0
apRuneReq:
.int 0
apRuneCount:
.int 0
apRuneDone:
.int 0
apNotifyReq:
.int 0
apNotifyDone:
.int 0
apHookMask:
.int 0
apHook0:
.int 0
apHook1:
.int 0
apHook2:
.int 0
apHook3:
.int 0
apHook4:
.int 0
apHook5:
.int 0
apHook6:
.int 0
apHook7:
.int 0
apHook8:
.int 0
apPickUpThis:
.int 0
apScreenThis:
.int 0
apDuration:
.int 0
apSaveF1:
.int 0
apListThis:
.int 0
apIterPtr:
.int 0
apIterLeft:
.int 0
apCandidate:
.int 0
apCandidate2:
.int 0

; sead::SafeString = { const char* cstr; void* vtable }
apNameCstr:
.int 0
apNameVtable:
.int 0

; tampon de 64 octets ou Python ecrit le nom d'acteur
apItemName:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; tampon de TEXTE LIBRE, 256 octets (128 caracteres UTF-16BE).
; Il n'est lu par aucune instruction : c'est une zone inscriptible dont
; l'adresse invitee est stable, pour y loger une chaine et faire pointer
; le jeu dessus. Place APRES apItemName pour ne decaler aucun champ deja
; cartographie dans mailbox.py.
apText:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- sondes du message central (MainScreen) ---------------------------
; Six fonctions vont chercher un message dans LayoutMsg/MainScreen_00 ou
; manipulent l'ecran MainScreen. On cherche celle qui est declenchee
; exactement une fois quand le bandeau central apparait -- meme methode
; que pour PickUpWin, ou neuf sondes avaient designe 0x02FFA888.
apMSMask:
.int 0
apMS0:
.int 0
apMS1:
.int 0
apMS2:
.int 0
apMS3:
.int 0
apMS4:
.int 0
apMS5:
.int 0
apMSThis:
.int 0
apMS1This:
.int 0
apMSReq:
.int 0
apMSIndex:
.int 0
apMSState:
.int 0
apMSDone:
.int 0
apMSQueue:
.int 0
apMSSaveQ:
.int 0
apMSRet:
.int 0
apMSFlag:
.int 0
; compteurs de trajet dans 0x02ed1e1c : par ou sort-elle vraiment ?
apMSPass:
.int 0
apMSBail:
.int 0
apMSBailA:
.int 0
apMSMid:
.int 0
apMSDbg8c:
.int 0
apMSDbg154:
.int 0
apMSDbg150:
.int 0
apMSDbgC:
.int 0
; capture des arguments de l'empilement 0x02ed1f7c(this, a, b)
apPushThis:
.int 0
apPushA:
.int 0
apPushB:
.int 0
apPushN:
.int 0
; valeurs a rejouer, et demande
apPlayA:
.int 0
apPlayB:
.int 0
apPlayReq:
.int 0
apPlayDone:
.int 0
; sead::SafeString a nous pour le parametre du message
apMsgCstr:
.int 0
apMsgVtable:
.int 0
apPlayRaw:
.int 0

; --- cadre bleu des conseils (MessageTipsRunTime_00) --------------------
; Huit sondes de comptage sur les fonctions du module 0x02fd3c74-0x02fd5340,
; celui qui va chercher LayoutMsg/MessageTipsRunTime_00. Meme protocole que
; pour PickUpWin et MainScreen : celle qui est declenchee une poignee de fois
; pendant que le cadre apparait est le point d'entree.
apTipsMask:
.int 0
apTips0:
.int 0
apTips1:
.int 0
apTips2:
.int 0
apTips3:
.int 0
apTips4:
.int 0
apTips5:
.int 0
apTips6:
.int 0
apTips7:
.int 0
apTipsThis:
.int 0
apTipsShowThis:
.int 0
apTipsShowIdx:
.int 0
apTipsReq:
.int 0
apTipsIndex:
.int 0
apTipsDone:
.int 0
apTipsTextReq:
.int 0
apTipsTextLen:
.int 0
apTipsTextDone:
.int 0
; ce que le JEU passe comme objet texte, releve au moment ou il l'affiche
apTipsSpyPtr:
.int 0
apTipsSpyLen:
.int 0
; sead::SafeString sur le nom du pane, construit par le cave
apPaneCstr:
.int 0
apPaneVtable:
.int 0
; notre objet texte { const char16_t* ; longueur }
apTipsStrPtr:
.int 0
apTipsStrLen:
.int 0

; --- traceur des recherches de libelle de message ----------------------
; 0x03a38ad0(archive, sortie, const char* libelle) est le point de passage
; obligatoire de TOUTE resolution de message : 35 sites l'appellent. La
; sonde est ancree apres son `mflr r0`, la ou r0 vaut encore l'adresse de
; retour -- donc le SITE d'appel, qui dit quel systeme demande le texte.
;
; Le tampon n'est pas circulaire : Python arme un quota (apRingLeft) et un
; pointeur, la sonde enregistre les N premieres resolutions puis s'arrete.
; Un anneau aurait demande un masquage, donc des instructions que
; l'assembleur de Cemu ne connait peut-etre pas -- et une seule inconnue
; fait rejeter tout le fichier.
apRingLeft:
.int 0
apRingPtr:
.int 0

; --- fenetre de dialogue (Message_00 / MessageSp_00) --------------------
; Chaine etablie par le traceur, puis par le desassemblage de ce qu'il a
; designe -- pas l'inverse :
;
;   0x035ff8fc(_, SafeString* archive, SafeString* libelle, a, b, drapeau)
;       ouvre la fenetre si besoin (0x033924c4(0x26,0)) puis, quand le
;       drapeau vaut 0, appelle
;   0x035fb5f8(this, archive, libelle)
;       qui resout le message et range le couple { texte, longueur } dans
;       this+0x1d0.
;
; Le premier argument de 0x035ff8fc est ignore : la fenetre est reprise
; d'un global. a et b ne sont pas devines, ils sont RELEVES sur un vrai
; appel du jeu et rejoues -- c'est ce qui avait sauve l'empilement du
; message central.
apDlgOpenN:
.int 0
apDlgOpen0N:
.int 0
apDlgSetN:
.int 0
apDlgThis:
.int 0
apDlgSeenArc:
.int 0
apDlgSeenLbl:
.int 0
apDlgArg6:
.int 0
apDlgArg7:
.int 0
apDlgArg8:
.int 0
apDlgReq:
.int 0
apDlgDone:
.int 0
apDlgTextReq:
.int 0
apDlgTextDone:
.int 0
apDlgStrPtr:
.int 0
apDlgStrLen:
.int 0
; sead::SafeString { cstr ; vtable } construits par le cave
apDlgArcCstr:
.int 0
apDlgArcVtable:
.int 0
apDlgLblCstr:
.int 0
apDlgLblVtable:
.int 0
; tampons ou Python ecrit le chemin d'archive et le libelle, en ASCII
apArcBuf:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
apLblBuf:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
apRing:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- tampon de texte de la fenetre de dialogue -------------------------
; 4096 octets, soit 2048 unites UTF-16. Distinct d'apText, qui fait 256
; octets et sert deja a la notification et au message central.
; Il ne faut pas le dimensionner sur le porteur : on n'ecrase pas l'arene,
; on fait pointer this+0x1d0 ICI. Le jeu embarque lui-meme un message de
; 481 unites (DemoMsg/Demo033_0/talk01), donc la fenetre encaisse bien
; plus que les 86 unites du porteur choisi. Mesure : 309 unites passent,
; en trois pages de trois lignes. Cemu dimensionne la cave sur le patch
; (5648 octets a ce stade), agrandir le tampon ne coute donc rien.
apDlgBuf:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- interception des ramassages ---------------------------------------
; itemGet n'a qu'UNE sortie, et son epilogue est autonome :
;
;   0x02eb5894  lmw   r18, 0x30(r1)
;   0x02eb5898  lwz   r0, 0x6c(r1)
;   0x02eb589c  mtlr  r0
;   0x02eb58a0  addi  r1, r1, 0x68
;   0x02eb58a4  blr
;
; Au point d'ancrage 0x02EB5400 le prologue est termine et l'instruction
; qu'on rejoue est justement celle qui sauve LR en 0x6c(r1). Sauter a
; l'epilogue rend donc la fonction inoffensive avec une pile et des
; registres parfaitement equilibres : rien n'est ajoute a l'inventaire,
; et l'appelant ne voit aucune difference.
;
; Le journal sert au FILTRE : r0 vaut encore l'adresse de retour, donc le
; SITE d'appel. Reste a mesurer s'il distingue un coffre d'une pomme.
apIgLeft:
.int 0
apIgPtr:
.int 0
apBlockReq:
.int 0
apBlockDone:
.int 0
; Marqueur pose par la fonction des objets ACCORDES (0x02b769c4) juste
; avant qu'elle n'appelle itemGet. Il permet de filtrer sans comparer
; d'adresses : comparer r0 a une borne demanderait cmplw ou subf, des
; instructions que l'assembleur de Cemu ne connait peut-etre pas -- et
; une seule inconnue fait rejeter tout le fichier. Un drapeau pose par
; une sonde et lu par une autre n'utilise que du cmpwi.
apGrantMark:
.int 0
; compte d'IMAGES restantes, pas un booleen : voir la soupape
; dans le hook per-frame. Depuis la mailbox 0x0BADF00E, cette lease
; n'autorise QUE le filtre Obj_DungeonClearSeal ci-dessous. Les coffres,
; Korogus et cadeaux de PNJ ne sont jamais bloques par cette commande.
apBlockGrants:
.int 0
apGrantN:
.int 0
apIgRing:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; sauvegarde des registres volatils autour de l'appel
apS0:
.int 0
apS3:
.int 0
apS4:
.int 0
apS5:
.int 0
apS6:
.int 0
apS7:
.int 0
apS8:
.int 0
apS9:
.int 0
apS10:
.int 0
apSLR:
.int 0
apSCTR:
.int 0

; --- fenetre d'obtention d'objet (MessageGet_00) -------------------------
; Dix-neuf sondes de comptage sur les fonctions de 0x02fcf29c a 0x02fd33e0,
; le module qui reference LayoutMsg/MessageGet_00, MessageGet_00Screen et
; MessageGet_00 -- les trois chaines que relocs.py fait remonter a cette
; plage. Meme protocole que PickUpWin, MainScreen et le cadre des conseils :
; celle qui est declenchee une poignee de fois quand la fenetre apparait est
; le point d'entree, celles qui comptent par centaines sont du per-frame.
;
; Pas de masque de bits ici, contrairement aux bancs precedents : a dix-neuf
; sondes il faudrait `oris` pour les bits 16 a 18, et une seule instruction
; que l'assembleur de Cemu ignore fait rejeter tout le fichier. Les compteurs
; portent deja l'information -- un compteur non nul EST le bit allume.
;
; Ces champs sont ajoutes en fin de bloc a dessein : inserer au milieu
; decalerait tout ce qui suit sans rien casser visiblement.
apGet0:                         ; fonction 0x02fcf29c
.int 0
apGet1:                         ; fonction 0x02fcf63c
.int 0
apGet2:                         ; fonction 0x02fd0314
.int 0
apGet3:                         ; fonction 0x02fd0ce4
.int 0
apGet4:                         ; fonction 0x02fd14e8
.int 0
apGet5:                         ; fonction 0x02fd1534
.int 0
apGet6:                         ; fonction 0x02fd165c
.int 0
apGet7:                         ; fonction 0x02fd1ed8
.int 0
apGet8:                         ; fonction 0x02fd20cc
.int 0
apGet9:                         ; fonction 0x02fd21cc
.int 0
apGet10:                         ; fonction 0x02fd22a0
.int 0
apGet11:                         ; fonction 0x02fd23f4
.int 0
apGet12:                         ; fonction 0x02fd2510
.int 0
apGet13:                         ; fonction 0x02fd255c
.int 0
apGet14:                         ; fonction 0x02fd2b18
.int 0
apGet15:                         ; fonction 0x02fd2d64
.int 0
apGet16:                         ; fonction 0x02fd2ff0
.int 0
apGet17:                         ; fonction 0x02fd3034
.int 0
apGet18:                         ; fonction 0x02fd33e0
.int 0

; Pour chaque sonde : d'ou vient l'appel, et avec quels arguments.
; L'adresse de retour tranche la seule question qui reste apres le comptage --
; laquelle de ces fonctions est appelee depuis l'EXTERIEUR du module. Celles
; qui s'appellent entre elles sont des etapes internes ; celle dont l'appelant
; est ailleurs est le point d'entree, celui qu'on pourra declencher soi-meme.
; r0 convient : au point d'ancrage le mflr a deja eu lieu, et le `bla` de Cemu
; ecrase LR, pas r0. r3/r4/r5 donnent les arguments a rejouer.
; adresse de retour
apGetFrom0:
.int 0
apGetFrom1:
.int 0
apGetFrom2:
.int 0
apGetFrom3:
.int 0
apGetFrom4:
.int 0
apGetFrom5:
.int 0
apGetFrom6:
.int 0
apGetFrom7:
.int 0
apGetFrom8:
.int 0
apGetFrom9:
.int 0
apGetFrom10:
.int 0
apGetFrom11:
.int 0
apGetFrom12:
.int 0
apGetFrom13:
.int 0
apGetFrom14:
.int 0
apGetFrom15:
.int 0
apGetFrom16:
.int 0
apGetFrom17:
.int 0
apGetFrom18:
.int 0
; r3
apGetThis0:
.int 0
apGetThis1:
.int 0
apGetThis2:
.int 0
apGetThis3:
.int 0
apGetThis4:
.int 0
apGetThis5:
.int 0
apGetThis6:
.int 0
apGetThis7:
.int 0
apGetThis8:
.int 0
apGetThis9:
.int 0
apGetThis10:
.int 0
apGetThis11:
.int 0
apGetThis12:
.int 0
apGetThis13:
.int 0
apGetThis14:
.int 0
apGetThis15:
.int 0
apGetThis16:
.int 0
apGetThis17:
.int 0
apGetThis18:
.int 0
; r4
apGetR4_0:
.int 0
apGetR4_1:
.int 0
apGetR4_2:
.int 0
apGetR4_3:
.int 0
apGetR4_4:
.int 0
apGetR4_5:
.int 0
apGetR4_6:
.int 0
apGetR4_7:
.int 0
apGetR4_8:
.int 0
apGetR4_9:
.int 0
apGetR4_10:
.int 0
apGetR4_11:
.int 0
apGetR4_12:
.int 0
apGetR4_13:
.int 0
apGetR4_14:
.int 0
apGetR4_15:
.int 0
apGetR4_16:
.int 0
apGetR4_17:
.int 0
apGetR4_18:
.int 0
; r5
apGetR5_0:
.int 0
apGetR5_1:
.int 0
apGetR5_2:
.int 0
apGetR5_3:
.int 0
apGetR5_4:
.int 0
apGetR5_5:
.int 0
apGetR5_6:
.int 0
apGetR5_7:
.int 0
apGetR5_8:
.int 0
apGetR5_9:
.int 0
apGetR5_10:
.int 0
apGetR5_11:
.int 0
apGetR5_12:
.int 0
apGetR5_13:
.int 0
apGetR5_14:
.int 0
apGetR5_15:
.int 0
apGetR5_16:
.int 0
apGetR5_17:
.int 0
apGetR5_18:
.int 0

; --- ordre des appels, et classe gestionnaire de la fenetre --------------
; apGetSeq est un compteur global : chaque sonde des deux bancs l'incremente
; et range sa valeur. Deux fonctions appelees une seule fois se classent donc
; l'une par rapport a l'autre, ce que des compteurs seuls ne disent pas -- or
; pour rejouer une sequence "preparer, remplir, afficher", l'ordre est
; precisement ce qu'il faut savoir.
apGetSeq:
.int 0
apGetOrd0:
.int 0
apGetOrd1:
.int 0
apGetOrd2:
.int 0
apGetOrd3:
.int 0
apGetOrd4:
.int 0
apGetOrd5:
.int 0
apGetOrd6:
.int 0
apGetOrd7:
.int 0
apGetOrd8:
.int 0
apGetOrd9:
.int 0
apGetOrd10:
.int 0
apGetOrd11:
.int 0
apGetOrd12:
.int 0
apGetOrd13:
.int 0
apGetOrd14:
.int 0
apGetOrd15:
.int 0
apGetOrd16:
.int 0
apGetOrd17:
.int 0
apGetOrd18:
.int 0

; Les 13 fonctions de 0x03606ad0 a 0x03607560. Le comptage a montre que les
; fonctions de la fenetre sont appelees depuis cette plage, et le balayage des
; `bl` de .text n'y trouve AUCUN appel direct : tout passe par vtable. Les
; appelants ne sont donc pas trouvables statiquement, seulement par la mesure.
; compteur
apGetWin0:
.int 0
apGetWin1:
.int 0
apGetWin2:
.int 0
apGetWin3:
.int 0
apGetWin4:
.int 0
apGetWin5:
.int 0
apGetWin6:
.int 0
apGetWin7:
.int 0
apGetWin8:
.int 0
apGetWin9:
.int 0
apGetWin10:
.int 0
apGetWin11:
.int 0
apGetWin12:
.int 0
; appelant
apGetWinFrom0:
.int 0
apGetWinFrom1:
.int 0
apGetWinFrom2:
.int 0
apGetWinFrom3:
.int 0
apGetWinFrom4:
.int 0
apGetWinFrom5:
.int 0
apGetWinFrom6:
.int 0
apGetWinFrom7:
.int 0
apGetWinFrom8:
.int 0
apGetWinFrom9:
.int 0
apGetWinFrom10:
.int 0
apGetWinFrom11:
.int 0
apGetWinFrom12:
.int 0
; r3
apGetWinThis0:
.int 0
apGetWinThis1:
.int 0
apGetWinThis2:
.int 0
apGetWinThis3:
.int 0
apGetWinThis4:
.int 0
apGetWinThis5:
.int 0
apGetWinThis6:
.int 0
apGetWinThis7:
.int 0
apGetWinThis8:
.int 0
apGetWinThis9:
.int 0
apGetWinThis10:
.int 0
apGetWinThis11:
.int 0
apGetWinThis12:
.int 0
; r4
apGetWinR4_0:
.int 0
apGetWinR4_1:
.int 0
apGetWinR4_2:
.int 0
apGetWinR4_3:
.int 0
apGetWinR4_4:
.int 0
apGetWinR4_5:
.int 0
apGetWinR4_6:
.int 0
apGetWinR4_7:
.int 0
apGetWinR4_8:
.int 0
apGetWinR4_9:
.int 0
apGetWinR4_10:
.int 0
apGetWinR4_11:
.int 0
apGetWinR4_12:
.int 0
; r5
apGetWinR5_0:
.int 0
apGetWinR5_1:
.int 0
apGetWinR5_2:
.int 0
apGetWinR5_3:
.int 0
apGetWinR5_4:
.int 0
apGetWinR5_5:
.int 0
apGetWinR5_6:
.int 0
apGetWinR5_7:
.int 0
apGetWinR5_8:
.int 0
apGetWinR5_9:
.int 0
apGetWinR5_10:
.int 0
apGetWinR5_11:
.int 0
apGetWinR5_12:
.int 0
; rang
apGetWinOrd0:
.int 0
apGetWinOrd1:
.int 0
apGetWinOrd2:
.int 0
apGetWinOrd3:
.int 0
apGetWinOrd4:
.int 0
apGetWinOrd5:
.int 0
apGetWinOrd6:
.int 0
apGetWinOrd7:
.int 0
apGetWinOrd8:
.int 0
apGetWinOrd9:
.int 0
apGetWinOrd10:
.int 0
apGetWinOrd11:
.int 0
apGetWinOrd12:
.int 0

; --- pilote de la fenetre d'obtention : 0x03a3ec0c -----------------------
; La chronologie des deux bancs le designe : ses trois sites d'appel
; 0x03a3ede0, 0x03a3ee88 et 0x03a3eeac declenchent, dans cet ordre,
; 0x02fd0314, 0x03606f48 (qui ouvre l'ecran) et 0x02fd255c, tous sur le
; meme `this` que la fenetre.
;
; Son prologue construit une SafeString sur sa propre pile a partir de r6 --
; `lis r0, 0x1026` puis `addic r0, r0, 0x3910` donne 0x10263910, la meme
; vtable que celle d'itemGet -- et la range dans this+0x78. r6 est donc un
; `const char*`. C'est une LECTURE de desassemblage : la sonde ci-dessous
; existe pour la verifier au lieu de la croire.
apGetDrvN:
.int 0
apGetDrvFrom:
.int 0
apGetDrvThis:
.int 0
apGetDrvA4:
.int 0
apGetDrvA5:
.int 0
apGetDrvA6:
.int 0
apGetDrvA7:
.int 0
apGetDrvA8:
.int 0
apGetDrvA9:
.int 0
apGetDrvReq:
.int 0
apGetDrvDone:
.int 0
; notre propre chaine, substituee a r6 lors du rejeu (64 octets)
apGetDrvName:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- capture FILTREE du pilote, et texte des panneaux --------------------
; MESURE : 0x03a3ec0c n'est PAS propre a la fenetre d'obtention. Son r6 est le
; NOM DE L'ECRAN a ouvrir -- releve 'MessageGet_00' sur un coffre, puis
; 'PauseMenuInfo_00' quand le joueur a valide la popup. C'est un ouvreur
; d'ecran generique. Lui substituer notre texte a fait planter le jeu, qui a
; cherche un ecran de ce nom.
;
; Donc les champs apGetDrv* ci-dessus valent pour le DERNIER ecran ouvert,
; quel qu'il soit. Les champs apGetWinC* ci-dessous ne valent que pour
; MessageGet_00 : la sonde apGetProbe1, qui n'est traversee que par cet
; ecran-la, y recopie la capture en attente. Aucune comparaison d'adresse --
; le meme tour que le marqueur des objets accordes.
apGetWinOk:
.int 0
apGetWinCThis:
.int 0
apGetWinCA4:
.int 0
apGetWinCA5:
.int 0
apGetWinCA6:
.int 0
apGetWinCA7:
.int 0
apGetWinCA8:
.int 0
apGetWinCA9:
.int 0

; Trois sondes sur les appels du module a l'aide de texte de pane. Chacune
; releve les deux mots de la structure passee en r4 -- le meme couple que
; apTipsSpy avait releve sur le cadre des conseils.
apGetTxtN0:
.int 0
apGetTxtR3_0:
.int 0
apGetTxtW0_0:
.int 0
apGetTxtW1_0:
.int 0
apGetTxtN1:
.int 0
apGetTxtR3_1:
.int 0
apGetTxtW0_1:
.int 0
apGetTxtW1_1:
.int 0
apGetTxtN2:
.int 0
apGetTxtR3_2:
.int 0
apGetTxtW0_2:
.int 0
apGetTxtW1_2:
.int 0

; --- texte de la fenetre d'obtention : relever, puis substituer ----------
; MESURE : la sonde 2 passe un objet { ptr, vtable 0x10244e0c }, et non la
; vtable SafeString 0x10263910 des deux autres. Son ptr ne se lit pas comme
; chaine C -- premier octet nul -- donc ce n'est pas de l'ASCII. Plutot que
; de deviner l'encodage, la sonde en RECOPIE 64 octets ici : le decodage se
; fait hors ligne, ou l'on peut essayer sans risque.
;
; apGetTxtReq arme la substitution : a l'appel suivant, le pointeur de texte
; est remplace par apGetTxtOur. C'est une ECRITURE, pas un appel -- donc sans
; le risque qui a fait planter le rejeu de l'ouvreur d'ecran.
apGetTxtSaveR3:
.int 0
apGetTxtReq:
.int 0
apGetTxtDone:
.int 0
apGetTxtB0:
.int 0
apGetTxtB1:
.int 0
apGetTxtB2:
.int 0
apGetTxtB3:
.int 0
apGetTxtB4:
.int 0
apGetTxtB5:
.int 0
apGetTxtB6:
.int 0
apGetTxtB7:
.int 0
apGetTxtB8:
.int 0
apGetTxtB9:
.int 0
apGetTxtB10:
.int 0
apGetTxtB11:
.int 0
apGetTxtB12:
.int 0
apGetTxtB13:
.int 0
apGetTxtB14:
.int 0
apGetTxtB15:
.int 0
; notre propre texte, 128 octets = 64 unites UTF-16
apGetTxtOur:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- resolveur commun de texte de pane : 0x03082c70 ---------------------
; C'est lui qui contient 0x03082ccc, le site que msgring relevait. Et c'est
; lui que l'aide generique 0x030834b0 appelle apres avoir fabrique le libelle
; "<acteur>_Name" avec le format 0x1025dd58 ("%s_Name").
;
; La question que cette sonde tranche : le nom de l'objet passe-t-il par ici ?
; Le journal de msgring n'avait montre aucun <acteur>_Name, mais il n'observe
; que les appels a 0x03a38ad0 -- pas l'entree de 0x03082c70.
;
; Quatre captures successives apres armement, parce que la construction de la
; fenetre en declenche plusieurs et qu'on ignore le rang du nom d'objet. Pas
; d'indexation calculee : quatre blocs distincts, choisis au cmpwi. Une seule
; instruction inconnue de l'assembleur de Cemu ferait rejeter tout le fichier.
apResArm:
.int 0
apResN:
.int 0
apResSaveR3:
.int 0
apResA0:
.int 0
apResB0:
.int 0
apResC0:
.int 0
apResL0_0:
.int 0
apResL0_1:
.int 0
apResL0_2:
.int 0
apResL0_3:
.int 0
apResL0_4:
.int 0
apResL0_5:
.int 0
apResL0_6:
.int 0
apResL0_7:
.int 0
apResA1:
.int 0
apResB1:
.int 0
apResC1:
.int 0
apResL1_0:
.int 0
apResL1_1:
.int 0
apResL1_2:
.int 0
apResL1_3:
.int 0
apResL1_4:
.int 0
apResL1_5:
.int 0
apResL1_6:
.int 0
apResL1_7:
.int 0
apResA2:
.int 0
apResB2:
.int 0
apResC2:
.int 0
apResL2_0:
.int 0
apResL2_1:
.int 0
apResL2_2:
.int 0
apResL2_3:
.int 0
apResL2_4:
.int 0
apResL2_5:
.int 0
apResL2_6:
.int 0
apResL2_7:
.int 0
apResA3:
.int 0
apResB3:
.int 0
apResC3:
.int 0
apResL3_0:
.int 0
apResL3_1:
.int 0
apResL3_2:
.int 0
apResL3_3:
.int 0
apResL3_4:
.int 0
apResL3_5:
.int 0
apResL3_6:
.int 0
apResL3_7:
.int 0

; Adresse de retour de chaque capture du resolveur. Au point d'ancrage
; (0x03082c8c) le mflr a deja eu lieu et r0 vaut encore l'adresse de retour :
; elle designe donc le SITE qui demande la resolution. C'est ce qui manquait
; pour savoir ou poser la substitution -- la sortie du nom d'objet est en
; 0x0e2008xx et non sur la pile, donc l'appel ne vient pas du site lu au
; desassemblage.
apResRet0:
.int 0
apResRet1:
.int 0
apResRet2:
.int 0
apResRet3:
.int 0

; --- substitution du nom d'objet, sans toucher a l'arene ----------------
; MESURE : 'Item_Ore_E_Name' est resolu par 0x03082c70, demande depuis
; 0x030835c8. Ce site est suivi immediatement de l'epilogue, donc la valeur
; de retour du resolveur se propage a l'appelant : a 0x030835c8, r3 EST le
; texte resolu.
;
; Remplacer r3 par notre propre objet donne notre texte sans ecrire une seule
; fois dans l'arene -- donc sans renommer l'objet, meme temporairement, donc
; sans exposer l'inventaire au plantage des noms longs.
;
; La forme de l'objet renvoye n'est pas supposee : les quatre premiers mots
; sont recopies pour etre lus hors ligne avant qu'on arme quoi que ce soit.
apSubN:
.int 0
apSubOut:
.int 0
apSubW0:
.int 0
apSubW1:
.int 0
apSubW2:
.int 0
apSubW3:
.int 0
apSubReq:
.int 0
apSubDone:
.int 0
apSubSaveR4:
.int 0
apSubLen:
.int 0
apSubOutBuf:
.int 0
apSubO0:
.int 0
apSubO1:
.int 0
apSubO2:
.int 0
apSubO3:
.int 0
apSubO4:
.int 0
apSubO5:
.int 0
apSubO6:
.int 0
apSubO7:
.int 0
; notre objet de remplacement, forme a confirmer par la capture
apSubObj:
.int 0
.int 0
.int 0
.int 0
; notre texte UTF-16BE, 256 octets = 128 unites
apSubBuf:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- description de la fenetre, meme schema que le nom ------------------
; 'Item_Ore_E_Desc' est resolu depuis 0x03083860. Deux differences avec le
; site du nom, toutes deux mesurees :
;
;  1. l'instruction d'origine y est `lmw r27, 0x22c(r1)`, qui RESTAURE r29 --
;     or c'est r29 qui porte le tampon de sortie. La rejouer d'abord, comme
;     le veut l'usage, detruirait ce qu'on vient chercher. La sonde capture
;     donc AVANT, et rejoue en dernier.
;  2. `lmw` n'est pas dans notre desassembleur, et rien ne dit que
;     l'assembleur de Cemu la connaisse. Elle est rejouee en cinq `lwz`
;     equivalents : r27..r31 depuis 0x22c a 0x23c.
apSubDescN:
.int 0
apSubDescReq:
.int 0
apSubDescDone:
.int 0
apSubDescLen:
.int 0
apSubDescBuf:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- armement automatique sur objet ACCORDE -----------------------------
; MESURE : le site du titre (0x030835c8) est GENERIQUE -- il resout
; <acteur>_Name pour tout le jeu. Armer a la main puis ouvrir l'inventaire
; detourne le nom de l'objet regarde, pas celui du coffre. Constate en jeu.
;
; apSubAuto resout ca : c'est un COMPTE d'objets accordes. La sonde des objets
; accordes (0x02b769d4) le consomme et arme la substitution a ce moment-la --
; donc juste avant itemGet, donc avant que la fenetre ne resolve son texte, et
; JAMAIS pendant que le joueur consulte son inventaire.
;
; Le client remplit les tampons a l'avance et pose apSubAuto ; le cave choisit
; l'instant. C'est la meme division du travail que pour le blocage.
apSubAuto:
.int 0
apSubAutoN:
.int 0

; --- ouvrir la fenetre nous-memes : les DEUX appels enchaines -----------
; MESURE : trois plantages en ne rejouant que le second appel. Le site reel
; en fait deux, et le premier fabrique l'objet que le second recoit :
;
;   0x03a42ccc  lwz r3, 0x24(r27)     une fabrique, prise dans r27
;   0x03a42cd0  lwz r10, 0x0(r3)
;   0x03a42cd4  lwz r0, 0x14(r10)     vtable[0x14]
;   0x03a42ce4  bctrl                 -> r3 = l'objet ecran
;   0x03a42cec  lwz r12, 0xc(r3)
;   0x03a42cf0  lwz r0, 0x4c(r12)     vtable[0x4c] = 0x03a3ec0c
;   0x03a42d10  bctrl                 avec r4..r9 tires de r27,r31,r24,r28,r25,r26
;
; Rejouer le second seul revenait a ouvrir un ecran sans passer par sa
; fabrique. On capture donc les six registres du vrai site, et on rejoue les
; deux appels dans l'ordre.
apOpnN:
.int 0
apOpnThis:
.int 0
apOpn24:
.int 0
apOpn25:
.int 0
apOpn26:
.int 0
apOpn27:
.int 0
apOpn28:
.int 0
apOpn31:
.int 0
apOpnReq:
.int 0
apOpnDone:
.int 0

; Capture FILTREE du site d'ouverture. La sonde 0x03a42ce8 se declenche a
; CHAQUE ouverture d'ecran -- 40 fois dans une simple partie -- donc les six
; registres bruts valent pour le dernier ecran ouvert, quel qu'il soit. Meme
; erreur que pour le pilote, et corrigee de la meme facon : apGetProbe1, que
; seul MessageGet_00 traverse, fige la capture en attente.
apOpnOk:
.int 0
apOpnC24:
.int 0
apOpnC25:
.int 0
apOpnC26:
.int 0
apOpnC27:
.int 0
apOpnC28:
.int 0
apOpnC31:
.int 0

; --- de quel THREAD parle-t-on ? ----------------------------------------
; Piste jamais verifiee : le hook per-frame et le code d'interface ne
; tournent peut-etre pas sur la meme pile. Les valeurs de r1 relevees
; jusqu'ici allaient de 0x0e200830 a 0x12afbb58 -- deux zones tres eloignees.
; Si c'est bien deux threads, appeler l'ouvreur d'ecran depuis le hook
; per-frame le fait tourner au mauvais endroit, ce qui expliquerait quatre
; plantages sans qu'aucun argument ne soit en cause.
apR1Frame:
.int 0
apR1Ui:
.int 0
apR1Name:
.int 0
apR1Opn:
.int 0

; --- bisection du rejeu d'ouverture -------------------------------------
; Cinq plantages, le dernier plus tardif que les precedents. Plutot que de
; retenter l'ensemble, on coupe : apOpnStep a 1 n'appelle que la fabrique,
; a 2 enchaine l'ouverture. Et apOpnPhase avance a chaque etape, pour dire
; jusqu'ou on est alle si le processus survit assez pour etre lu.
;   1 = avant la fabrique   2 = fabrique revenue
;   3 = avant l'ouverture   4 = ouverture revenue
apOpnStep:
.int 0
apOpnPhase:
.int 0
apOpnR3:
.int 0

; --- l'objet de contexte r31, et son contenu ----------------------------
; MESURE decisive : r31 (0x443d6518) garde la meme ADRESSE d'une session a
; l'autre, mais son CONTENU change. Fenetre ouverte on lit
; `43 41 c9 3c 44 3d 63 c8` ; fenetre fermee, `00 00 00 01 00 00 00 00`.
; C'est un objet de contexte que le jeu remet a zero en refermant.
;
; Et la bisection le confirme : appeler la fabrique fenetre OUVERTE marche,
; fenetre fermee plante. On recopie donc son contenu au moment de la capture,
; pour le restaurer avant le rejeu.
;
; Reserve assumee : ces mots contiennent des pointeurs de tas. Les restaurer
; ne ressuscite pas ce qu'ils designent. Si le rejeu plante encore, c'est que
; l'objet ne suffit pas et qu'il faut remonter a ce qui le remplit.
apOpnCtxSave:
apOpnCtx0:
.int 0
apOpnCtx1:
.int 0
apOpnCtx2:
.int 0
apOpnCtx3:
.int 0
apOpnCtx4:
.int 0
apOpnCtx5:
.int 0
apOpnCtx6:
.int 0
apOpnCtx7:
.int 0
apOpnCtx8:
.int 0
apOpnCtx9:
.int 0
apOpnCtx10:
.int 0
apOpnCtx11:
.int 0
apOpnCtx12:
.int 0
apOpnCtx13:
.int 0
apOpnCtx14:
.int 0
apOpnCtx15:
.int 0
apOpnCtx16:
.int 0
apOpnCtx17:
.int 0
apOpnCtx18:
.int 0
apOpnCtx19:
.int 0
apOpnCtx20:
.int 0
apOpnCtx21:
.int 0
apOpnCtx22:
.int 0
apOpnCtx23:
.int 0
apOpnCtx24:
.int 0
apOpnCtx25:
.int 0
apOpnCtx26:
.int 0
apOpnCtx27:
.int 0
apOpnCtx28:
.int 0
apOpnCtx29:
.int 0
apOpnCtx30:
.int 0
apOpnCtx31:
.int 0
apOpnCtxR3:
.int 0

; --- le tas ------------------------------------------------------------
; MESURE : r31 n'est pas un objet de contexte, c'est un HEAP. La branche 11
; de la fabrique fait `li r3, 0x1c9c ; li r5, 4 ; bl 0x0308e5a0` en laissant
; r4 intact -- donc r4 EST le tas sur lequel l'ecran de 7324 octets est
; alloue. Fenetre fermee, ce tas est mort : l'allocation rend 0, et la
; fabrique rend 0. C'est tout le refus.
;
; Et l'allocateur gere le cas nul : 0x0308e514 teste `cmpwi r3, 0` et, si
; c'est nul, va chercher le TAS COURANT via 0x030aa1ac. Il suffit donc de ne
; pas passer notre tas mort.
;
; apOpnHeap a 0 = passer un tas nul (le courant) ; sinon = le tas capture.
apOpnHeap:
.int 0

; --- deux facons d'obtenir l'ecran --------------------------------------
; apOpnMode = 0 : la fabrique brute 0x0305eae8, telle que le vrai site
;   l'appelle. Elle alloue 7324 octets sur le tas passe en r4 -- et rend 0
;   des que ce tas est mort, ce qui est le cas hors ouverture. Tas nul :
;   l'allocateur cherche le tas COURANT (0x0308e514) et n'en trouve pas non
;   plus depuis notre thread. Mesure : rend 0 dans les deux cas.
;
; apOpnMode = 1 : le trampoline 0x033924c4, celui que la boite de dialogue
;   emploie deja avec succes depuis ce meme hook -- client_api.md le note
;   comme `0x033924c4(0x26, 0)`. Il saute vers *(0x1047e1a4), une API
;   enregistree qui se charge elle-meme du tas. On lui passe notre index,
;   0x0b, et zero. Le trampoline est sur : `bclr` si le pointeur est nul.
apOpnMode:
.int 0

; --- restaurer l'objet de contexte : desormais OPTIONNEL -----------------
; Ce bloc recopie 32 mots dans apOpnC31, qui est un TAS DEJA LIBERE. Ecrire
; dans l'en-tete d'un tas mort n'a jamais rien debloque et peut abimer
; l'allocateur. Il est donc coupe par defaut. Python le rallume avec --ctx
; pour reproduire les mesures anterieures.
apOpnCtxOn:
.int 0

; --- appeler la FONCTION ENGLOBANTE, pas le milieu -----------------------
; MESURE hors ligne (rpx.py dis 0x03a42b94) : r31 n'est pas une variable
; locale, c'est l'ARGUMENT 6 -- `mr r31, r8` au prologue. Et la fonction sait
; deja se passer d'un tas : quand r31 et r30 sont nuls, elle branche en
; 0x03a42c90 et en CREE un via `bl 0x030a8734`, puis reprend le meme chemin.
;
; Rejouer depuis 0x03a42ccc, c'est donc sauter par-dessus la creation du tas.
; apOpnMode = 2 appelle 0x03a42b94(arg1..arg6) en entier :
;   r3 = apOpnC27   r4 = apOpnArg4   r5 = apOpnC28
;   r6 = apOpnC25   r7 = apOpnC26    r8 = apOpnHeap
; Avec apOpnArg4 = 0 et apOpnHeap = 0, la fonction prend sa branche de
; creation. Rien n'est deref dans le code injecte : la fonction fait tout.
apOpnArg4:
.int 0

; --- d'ou vient un TAS VIVANT ? -----------------------------------------
; Le createur 0x030a857c et l'allocateur 0x0308e514 butent sur la MEME
; fonction : `0x030aa1ac(x)`, qui rend le tas courant. Son corps, lu hors
; ligne :
;     r12 = *(0x1046C920) ; r3 = *(r12+0x60) ; bl 0x0434c488 (import RPL)
;     si le retour est non nul -> rendre *(retour + 0x70)   <- tas du THREAD
;     sinon                    -> rendre *(argument + 0x4)  <- repli statique
; C'est donc thread-local, et il existe un repli statique. Le createur lui
; passe *(0x1046C8B0).
;
; NOTE : le handoff ecrivait 0x1047c8b0. Le code fait `lis r3, 0x1047 ;
; lwz r3, -0x3750(r3)`, soit 0x10470000 - 0x3750 = 0x1046C8B0. L'ecart d'un
; 0x10000 aurait envoye lire dans le vide.
;
; Cette sonde repond sans rien risquer : elle lit les deux statiques, puis
; appelle le getter -- mais seulement si ses deux deref sont surs.
apHeapReq:
.int 0
apHeapN:
.int 0
apHeapRoot:
.int 0
apHeapMgr:
.int 0
apHeapFb:
.int 0
apHeapCur:
.int 0

; --- le prologue de 0x03a42b94 : les six arguments, et l'appelant --------
; Ancree sur `stw r0, 0x34(r1)`, ou r0 porte encore LR et ou aucun `mr` n'a
; detruit r3..r8. Brute d'abord (le site s'ouvre 40 fois par partie), puis
; figee par apGetProbe1, que seul MessageGet_00 traverse.
apOpnProN:
.int 0
apOpnProLr:
.int 0
apOpnProR1:
.int 0
apOpnProA1:
.int 0
apOpnProA2:
.int 0
apOpnProA3:
.int 0
apOpnProA4:
.int 0
apOpnProA5:
.int 0
apOpnProA6:
.int 0
apOpnPrcOk:
.int 0
apOpnPrcLr:
.int 0
apOpnPrcR1:
.int 0
apOpnPrcA1:
.int 0
apOpnPrcA2:
.int 0
apOpnPrcA3:
.int 0
apOpnPrcA4:
.int 0
apOpnPrcA5:
.int 0
apOpnPrcA6:
.int 0

; --- l'etage AU-DESSUS : 0x030806f0 -------------------------------------
; MESURE du 22/08 (getprobe, deux traces) : rejouer 0x03a42b94 reproduit tout
; le groupe de CONSTRUCTION -- chaque fonction y passe de 1 a 2 appels -- mais
; aucune du groupe d'AFFICHAGE (0x02fd0ce4, 0x02fd1534, 0x02fd14e8,
; 0x02fd165c, 0x02fd2b18, 0x02fd20cc). Ces six-la sont appelees depuis
; 0x036072e0, 0x03607390 et 0x03607414, pas depuis 0x03a42b94.
;
; Et 0x03a42b94 n'est pas le sommet : son appelant 0x030806f0 fait 40
; instructions de plus apres l'appel, dont `0x03a3f36c(ecran, 1)`. On monte
; donc d'un cran, avec le meme protocole qui vient de marcher : sonde sur le
; prologue, capture figee par apGetProbe1, puis rejeu.
;
; Ancre : `stw r0, 0x2c(r1)` en 0x0308070c. Le mflr a eu lieu en 0x030806f8,
; et les `mr` du prologue ont recopie r3..r7 sans les detruire -- r7 n'est
; meme copie qu'en 0x03080710, apres l'ancre.
apUpN:
.int 0
apUpLr:
.int 0
apUpR1:
.int 0
apUpA1:
.int 0
apUpA2:
.int 0
apUpA3:
.int 0
apUpA4:
.int 0
apUpA5:
.int 0
apUpcOk:
.int 0
apUpcA1:
.int 0
apUpcA2:
.int 0
apUpcA3:
.int 0
apUpcA4:
.int 0
apUpcA5:
.int 0

; --- LA MISE EN SCENE, relevee en 0x03a40ebc ----------------------------
; MESURE : ni le tas, ni les etages superieurs, ni l'etat interne de l'ecran,
; ni le tableau des actifs a +0x604 ne font apparaitre la fenetre. Le geste
; qui manque est juste avant l'appel que la chronologie designait :
;
;   0x03a40e9c  vtable[0x214](ecran, "open")   ; si mode 1 ou 2
;   0x03a40ec4  stb 0, 0x9e(ecran)
;   0x03a40ec8  stb 1, 0x96(ecran)
;   0x03a40ecc  stb 0, 0x97(ecran)
;   0x03a40edc  vtable[0x114](ecran)           ; = 0x036072e0
;
; Le `0x9e = 0` recoupe la photographie de l'objet : c'etait le seul bit de
; +0x9c qui differait entre affiche et construit. On l'avait ecrit sans rien
; appeler -- c'est l'appel qui manquait, pas le drapeau.
;
; vtable[0x114] et vtable[0x214] se lisent dans le RPX : 0x036072e0 et
; 0x02fd299c, et la chaine 0x1035DB30 est "open".
apOpnAnim:
.int 0

; --- LA MISE EN SCENE EST UNE METHODE VIRTUELLE -------------------------
; 0x03a40d20 apparait dans 94 vtables : ce n'est pas une fonction libre,
; c'est une fente. Sur notre ecran (vtable 0x10245298) elle est en
; +0x1a4, et ses voisines sont exactement les quatre appelants du groupe
; d'affichage que la chronologie disait manquant :
;
;   +0x1a4  0x03a40d20   la mise en scene
;   +0x1b4  0x03a40f40   -> 0x03607390
;   +0x1c4  0x03a4115c   -> 0x03607414
;   +0x1cc  0x03a411a0   -> 0x036074b8
;
; Signature : 0x03a40d20(ecran, mode), un switch sur mode 0..4. L'animation
; "open" n'est jouee que pour 1 et 2, et le mode 1 fait tout un preambule --
; vtable[0x94] puis 0x03a31898 sur ecran->0x18 -- que nos quatre gestes a la
; main sautaient. C'est la piste la plus serieuse pour le plantage de
; vtable[0x214] appelee nue.
;
; apOpnMode = 5 appelle ecran->vtable[0x1a4](ecran, apOpnVArg).
apOpnVArg:
.int 0

; --- LE SOMMET DE LA CHAINE : 0x02b769c4 --------------------------------
; On construit la fenetre PAR LE BAS depuis le debut, et on bute chaque fois
; sur une piece de contexte manquante. L'ecran est desormais dans le meme etat
; que l'affiche sur tous les champs mesures, et il ne se dessine toujours pas :
; trois fonctions ne se declenchent jamais, toutes appelees HORS du
; gestionnaire d'ecrans (0x03a3b8c4, 0x0339c664, 0x036073c4).
;
; Donc on change d'echelle. 0x02b769c4 est la fonction qui traite les objets
; ACCORDES -- coffre, sanctuaire, Korogu, cadeau de PNJ -- deja identifiee par
; le filtre d'itemspy. La rejouer, c'est laisser le jeu tout faire lui-meme :
; fenetre, animation, texte, attente de la touche A.
;
; Signature : 0x02b769c4(r3, r4). Les deux sont intacts a l'ancre 0x02b769d4,
; ou apGrantSpy est deja posee -- le `mr r31, r4` est avant, le `mr r30, r3`
; apres, et aucun des deux ne detruit sa source.
apGrantR3:
.int 0
apGrantR4:
.int 0
apGrantLr:
.int 0

; --- la structure de PILE que r4 designe ---------------------------------
; MESURE : r4 vaut 0x12b3c4f8, une adresse de PILE. Au rejeu ce cadre est
; mort depuis longtemps et on passait des octets qui ne veulent plus rien
; dire -- le rejeu n'etait pas fidele. Monter d'un cran n'aide pas :
; 0x02b77260 ne fait que relayer le meme pointeur, il vient de plus haut.
;
; Mais rien n'oblige a garder l'original : on RECOPIE 128 octets pendant que
; le cadre est vivant, et on passe notre copie au rejeu. Python ecrit
; l'adresse de la copie dans apGrantBufPtr -- ainsi le code injecte n'a pas
; besoin de calculer une adresse absolue, idiome dont on ignore si
; l'assembleur de Cemu l'accepte.
apGrantBufPtr:
.int 0

; --- LA DIFFUSION : 0x032bc730(dispatcher, nomObjet) --------------------
; MESURE : 0x02b769c4 appelle itemGet en 0x02b76ac0, puis -- sur CHACUNE de
; ses branches, trois fois dans la fonction -- fait :
;     lwz r3, *(0x1047D6C0)   ; un statique
;     mr  r4, r30             ; la chaine du nom d'objet
;     bl  0x032bc730
; Et 0x032bc730 parcourt une LISTE d'abonnes (compte en +0x58, tableau en
; +0x60) en appelant une methode virtuelle sur chacun. C'est une diffusion
; d'evenement : "l'objet X vient d'etre obtenu". L'interface s'y abonne
; vraisemblablement pour ouvrir la fenetre.
;
; Deux arguments, un statique et un nom -- le candidat le plus propre de la
; session. apGrantName permet de passer NOTRE chaine plutot que la capturee.
apDispN:
.int 0
apDispR3:
.int 0
apDispR4:
.int 0
apDispLr:
.int 0
apGrantName:
.int 0
; Le dispatcher n'est plus CALCULE mais MESURE : apDispSpy le releve sur un
; vrai coffre, et Python le recopie ici. Une premiere version derivait
; 0x1047D6C0 de `lis 0x1047 / lwz -0x2940` -- l'adresse reelle est
; 0x1046D6C0, et l'ecart d'un 0x10000 faisait passer la chaine rodata
; 'WeatherSelector' pour un objet. Le jeu est mort dessus. Meme piege que
; celui deja corrige sur 0x1046C8B0 dans le handoff : ne plus jamais deriver
; une adresse statique a la main quand une sonde peut la relever.
apDispArg:
.int 0

; --- LA CHAINE D'APPEL COMPLETE, d'un seul coup -------------------------
; On a remonte la chaine un cran par session, et chaque cran revelait un
; morceau de contexte manquant : un tas, un pilote, une pile. C'est le
; symptome d'un systeme ou la fenetre n'est pas un objet qu'on ouvre mais
; l'affichage d'un ETAT dans lequel le jeu entre -- Link fige, commandes
; verrouillees, attente de A. La preuve la plus nette : eteindre l'octet
; d'affichage d'une VRAIE fenetre empeche de la valider, donc le jeu attend
; toujours.
;
; Sur PowerPC les cadres de pile sont chaines : *(r1) donne le cadre
; precedent, et *(cadre + 4) l'adresse de retour. En deroulant ce chainage
; depuis l'attribution d'objet, on obtient TOUTE la chaine d'appel du vrai
; coffre -- jusqu'au systeme d'evenement. Une seule mesure au lieu d'un
; barreau par session.
;
; Seuls r11 et r12 sont libres dans une sonde, donc on range le cadre courant
; en memoire entre chaque etape plutot que de le garder en registre. Chaque
; deref est precede d'un test a zero : une pile mal formee arrete le
; deroulage au lieu de tuer le jeu.
; --- UN INVOCATEUR GENERIQUE -------------------------------------------
; On a modifie le patch une fois par experience, et chaque modification coute
; une fermeture de Cemu et un rechargement de partie. apOpnMode = 8 appelle
; l'adresse rangee dans apCallAddr avec les huit arguments d'apCallA1..A8.
; Python decide de tout ; le cave ne fait que sauter. Plus aucune experience
; d'appel ne demandera de redemarrage.
;
; La seule garde possible ici est celle du saut : une adresse hors de .text
; est refusee. Les arguments, eux, sont sous la responsabilite de Python --
; c'est lui qui peut lire la memoire et verifier avant de tirer.
apCallAddr:
.int 0
apCallA1:
.int 0
apCallA2:
.int 0
apCallA3:
.int 0
apCallA4:
.int 0
apCallA5:
.int 0
apCallA6:
.int 0
apCallA7:
.int 0
apCallA8:
.int 0
apCallRet:
.int 0
apCallN:
.int 0
apLvl0N:
.int 0
apLvl0R3:
.int 0
apLvl0R4:
.int 0
apLvl0R5:
.int 0
apLvl0R6:
.int 0
apLvl0R7:
.int 0
apLvl0Lr:
.int 0
apLvl1N:
.int 0
apLvl1R3:
.int 0
apLvl1R4:
.int 0
apLvl1R5:
.int 0
apLvl1R6:
.int 0
apLvl1R7:
.int 0
apLvl1Lr:
.int 0
apLvl2N:
.int 0
apLvl2R3:
.int 0
apLvl2R4:
.int 0
apLvl2R5:
.int 0
apLvl2R6:
.int 0
apLvl2R7:
.int 0
apLvl2Lr:
.int 0
apLvl3N:
.int 0
apLvl3R3:
.int 0
apLvl3R4:
.int 0
apLvl3R5:
.int 0
apLvl3R6:
.int 0
apLvl3R7:
.int 0
apLvl3Lr:
.int 0
apLvl4N:
.int 0
apLvl4R3:
.int 0
apLvl4R4:
.int 0
apLvl4R5:
.int 0
apLvl4R6:
.int 0
apLvl4R7:
.int 0
apLvl4Lr:
.int 0
apLvl5N:
.int 0
apLvl5R3:
.int 0
apLvl5R4:
.int 0
apLvl5R5:
.int 0
apLvl5R6:
.int 0
apLvl5R7:
.int 0
apLvl5Lr:
.int 0
apLvl6N:
.int 0
apLvl6R3:
.int 0
apLvl6R4:
.int 0
apLvl6R5:
.int 0
apLvl6R6:
.int 0
apLvl6R7:
.int 0
apLvl6Lr:
.int 0
apLvl7N:
.int 0
apLvl7R3:
.int 0
apLvl7R4:
.int 0
apLvl7R5:
.int 0
apLvl7R6:
.int 0
apLvl7R7:
.int 0
apLvl7Lr:
.int 0
apLvl8N:
.int 0
apLvl8R3:
.int 0
apLvl8R4:
.int 0
apLvl8R5:
.int 0
apLvl8R6:
.int 0
apLvl8R7:
.int 0
apLvl8Lr:
.int 0
apLvl10N:
.int 0
apLvl10R3:
.int 0
apLvl10R4:
.int 0
apLvl10R5:
.int 0
apLvl10R6:
.int 0
apLvl10R7:
.int 0
apLvl10Lr:
.int 0
apLvl11N:
.int 0
apLvl11R3:
.int 0
apLvl11R4:
.int 0
apLvl11R5:
.int 0
apLvl11R6:
.int 0
apLvl11R7:
.int 0
apLvl11Lr:
.int 0
apLvl13N:
.int 0
apLvl13R3:
.int 0
apLvl13R4:
.int 0
apLvl13R5:
.int 0
apLvl13R6:
.int 0
apLvl13R7:
.int 0
apLvl13Lr:
.int 0

; --- et les DOUZE niveaux de la chaine d'appel, sondes d'un coup --------
; Le deroulage de pile a donne la chaine complete du vrai coffre. Plutot que
; de remonter un cran par session -- ce qui a coute la journee -- on capture
; les arguments des douze niveaux en une fois. Celui dont TOUS les arguments
; sont persistants (statique ou tas, pas pile) sera rejouable tel quel.
; --- ET LA CHAINE D'APPEL DE LA FENETRE ELLE-MEME ----------------------
; ERREUR DE CADRAGE corrigee : on a deroule la pile du DON D'OBJET, alors
; qu'on veut celle de la FENETRE. Ouvrir un coffre lance un enchainement
; d'actions -- donner l'objet en est une, afficher la fenetre et figer Link
; en est une autre. Le deroulage du grant menait a 0x021c0308, qui ne fait
; que rappeler le chemin d'attribution deja rejoue sans succes.
;
; Meme mecanique, mais ancree sur la CREATION DE L'ECRAN, ou apOpnProSpy est
; deja posee. Cette chaine-la remonte a ce qui decide d'afficher.
; --- MAINTENIR LA FENETRE OUVERTE ---------------------------------------
; MESURE : appelee correctement, la fenetre s'ouvre ENTIEREMENT -- la
; chronologie montre pour la premiere fois 0x036074b8, la quatrieme etape de
; transition -- puis se referme en TROIS IMAGES. +0x94 porte le bit 0x100
; (demande de fermeture) des le premier echantillon, l'octet d'activite
; retombe a 40 ms, l'ecran est detruit a 80 ms.
;
; Dans le vrai jeu c'est l'EVENEMENT qui la retient en attendant la touche A.
; Python ne peut pas le remplacer : un acces memoire inter-processus coute
; des millisecondes, et la boucle n'a corrige que 3 fois pendant que l'ecran
; mourait. Il faut agir ICI, une fois par image.
;
; apHoldN est un COMPTE D'IMAGES, pas un booleen : si le client Python meurt,
; le maintien s'eteint tout seul. Meme soupape que apBlockGrants -- sans
; elle, une fenetre coincee resterait sans que le joueur puisse s'en sortir.
;
; On ECRIT une valeur fixe plutot que d'effacer un bit : effacer demanderait
; rlwinm ou andi, dont on ignore si l'assembleur de Cemu les accepte. 0x200
; est la valeur mesuree sur une fenetre affichee.
apHoldN:
.int 0
apHoldQ:
.int 0
apWStkF:
.int 0
apWStkL0:
.int 0
apWStkL1:
.int 0
apWStkL2:
.int 0
apWStkL3:
.int 0
apWStkL4:
.int 0
apWStkL5:
.int 0
apWStkL6:
.int 0
apWStkL7:
.int 0
apWStkL8:
.int 0
apWStkL9:
.int 0
apWStkL10:
.int 0
apWStkL11:
.int 0
apWStkL12:
.int 0
apWStkL13:
.int 0
apStkF:
.int 0
apStkL0:
.int 0
apStkL1:
.int 0
apStkL2:
.int 0
apStkL3:
.int 0
apStkL4:
.int 0
apStkL5:
.int 0
apStkL6:
.int 0
apStkL7:
.int 0
apStkL8:
.int 0
apStkL9:
.int 0
apStkL10:
.int 0
apStkL11:
.int 0
apStkL12:
.int 0
apStkL13:
.int 0
apGrantBuf:
apGrantW0:
.int 0
apGrantW1:
.int 0
apGrantW2:
.int 0
apGrantW3:
.int 0
apGrantW4:
.int 0
apGrantW5:
.int 0
apGrantW6:
.int 0
apGrantW7:
.int 0
apGrantW8:
.int 0
apGrantW9:
.int 0
apGrantW10:
.int 0
apGrantW11:
.int 0
apGrantW12:
.int 0
apGrantW13:
.int 0
apGrantW14:
.int 0
apGrantW15:
.int 0
apGrantW16:
.int 0
apGrantW17:
.int 0
apGrantW18:
.int 0
apGrantW19:
.int 0
apGrantW20:
.int 0
apGrantW21:
.int 0
apGrantW22:
.int 0
apGrantW23:
.int 0
apGrantW24:
.int 0
apGrantW25:
.int 0
apGrantW26:
.int 0
apGrantW27:
.int 0
apGrantW28:
.int 0
apGrantW29:
.int 0
apGrantW30:
.int 0
apGrantW31:
.int 0

; --- et on MESURE le mode plutot que de le deviner ----------------------
; 0x03a40d20 sert 94 classes, donc la sonde voit passer d'autres ecrans. Pas
; de comparaison en assembleur : on ignore si Cemu accepte cmplw, et le
; projet a deja paye cher une instruction supposee. On tient donc un registre
; a decalage de 8 entrees, en lwz/stw seulement, et c'est Python qui
; reconnait notre ecran dedans.
apShowN:
.int 0
apShowT0:
.int 0
apShowT1:
.int 0
apShowT2:
.int 0
apShowT3:
.int 0
apShowT4:
.int 0
apShowT5:
.int 0
apShowT6:
.int 0
apShowT7:
.int 0
apShowM0:
.int 0
apShowM1:
.int 0
apShowM2:
.int 0
apShowM3:
.int 0
apShowM4:
.int 0
apShowM5:
.int 0
apShowM6:
.int 0
apShowM7:
.int 0
apShowL0:
.int 0
apShowL1:
.int 0
apShowL2:
.int 0
apShowL3:
.int 0
apShowL4:
.int 0
apShowL5:
.int 0
apShowL6:
.int 0
apShowL7:
.int 0

; --- invocateur GENERIQUE sur le hook per-frame -----------------------
; L'autre invocateur (apOpnMode 8) vit dans apGetWinProbe6, une fonction
; du pilote de MessageGet_00, et le patch le garde derriere apOpnOk.
; Consequence mesuree : a froid AUCUN appel ne part, et la requete reste
; EN ATTENTE puis s'execute au prochain vrai coffre, qui affiche alors
; notre objet. Ce bloc-ci tourne depuis le demarrage, sans prerequis.
; Il partage apCallAddr / apCallA1..A8 / apCallRet / apCallN.
apPfReq:
.int 0

; --- resolution statique des pointeurs de canaux ------------------------
; apResolveN compte les passages du resolveur. C'est le GARDE-FOU du piege
; « champ ajoute en fin de bloc » : tant que Cemu n'a pas ete ferme et
; rouvert, ces deux mots tombent sur du CODE et se lisent sans erreur. Un
; compteur d'images ne peut pas depasser apTick -- c'est l'invariant qui
; tranche, cote Python, entre « resolveur present » et « patch perime ».
apResolveN:
.int 0
; La table d'ecrans (gestionnaire+0x18), 0 tant que l'IHM n'est pas prete.
; Sert aussi de temoin d'IHM vivante : 0x035ff8fc dereference le
; gestionnaire d'ecrans sans le tester, donc rien ne doit partir avant.
apScrTable:
.int 0
.align 4

apProbe:
    stw   r0, 0x78(r30)         ; --- ORIGINE hook 1 ---

    lis   r11, apTick@ha

    lwz   r12, apTick@l(r11)
    addi  r12, r12, 1
    stw   r12, apTick@l(r11)
    stw   r1, apR1Frame@l(r11)      ; sur quelle pile tourne ce hook ?

apResolve:
    ; --- RESOUDRE les pointeurs des canaux, au lieu de les CAPTURER ---------
    ; Jusqu'ici chaque canal attendait qu'une sonde voie passer son objet :
    ; il fallait donc ramasser un objet, declencher un message central et
    ; voir une vraie boite de dialogue A CHAQUE lancement du jeu avant que
    ; quoi que ce soit reponde. Les quatre pointeurs sont pourtant tous
    ; joignables depuis des globales :
    ;
    ;   PauseMenuDataMgr   *(0x10469978)                    singleton
    ;   PickUpWin          table d'ecrans [0x28]
    ;   message central    *(table[0x25] + 0x1b84)
    ;   boite de dialogue  table[0x26]     (creee a la demande par le jeu)
    ;
    ; Chaque valeur est reecrite A CHAQUE IMAGE : un ecran detruit puis
    ; recree (la boite de dialogue l'est systematiquement) ne laisse donc
    ; jamais de pointeur perime derriere lui. Mais un champ de CAPTURE n'est
    ; jamais remis a zero : si la source vaut 0, on passe. Ainsi le resolveur
    ; ne peut qu'ajouter, jamais detruire ce que les sondes savaient deja.
    ; apScrTable, lui, est notre propre temoin : il est remis a 0 chaque
    ; image, sinon il survivrait a la mort de l'IHM et mentirait.
    ;
    ; Ne detruit que r12 : r11 reste la page du cave d'un bout a l'autre,
    ; et apScrTable sert de variable de travail entre les etapes.

    lis   r12, 0x1046
    ori   r12, r12, 0x9978
    lwz   r12, 0(r12)               ; *(0x10469978) = PauseMenuDataMgr
    cmpwi r12, 0
    beq   apResolveScr
    stw   r12, apPmdmThis@l(r11)

apResolveScr:
    li    r12, 0
    stw   r12, apScrTable@l(r11)    ; 0 par defaut : IHM pas prete
    lis   r12, 0x1047
    ori   r12, r12, 0xe650
    lwz   r12, 0(r12)               ; *(0x1047E650) = gestionnaire d'ecrans
    cmpwi r12, 0
    beq   apResolveDone
    lwz   r12, 0x14(r12)            ; nombre d'emplacements

    ; --- refuser tout ce qui n'est pas la table mesuree ---------------------
    ; Le jeu lui-meme n'indexe la table que si l'index tient dans ce compte ;
    ; sinon il retombe sur l'emplacement 0. Plutot que de rejouer ce repli --
    ; qui rendrait un ECRAN QUELCONQUE et le ferait passer pour le notre --
    ; on exige les 99 emplacements releves sur 1.5.0 EUR. Toute autre valeur
    ; laisse apScrTable a 0 : les outils refusent proprement.
    cmpwi r12, 0x63
    bne   apResolveDone

    lis   r12, 0x1047
    ori   r12, r12, 0xe650
    lwz   r12, 0(r12)
    lwz   r12, 0x18(r12)            ; la table des 99 ecrans
    cmpwi r12, 0
    beq   apResolveDone
    stw   r12, apScrTable@l(r11)

    ; --- notification d'objet : ecran 0x28 (PickUpWin) ----------------------
    ; Index etabli par mesure : c'est le seul ecran dont +0x1b68 porte un pool
    ; de 7 lignes de 0x14c octets -- la disposition que la boucle d'empilement
    ; parcourt (0x3c = compte, 0x44 = tableau, ligne+0x149 = rang).
    lwz   r12, 0xa0(r12)            ; 0x28 * 4
    cmpwi r12, 0
    beq   apResolveMs
    stw   r12, apScreenThis@l(r11)
    addi  r12, r12, 0x1b68
    stw   r12, apListThis@l(r11)

apResolveMs:
    ; --- message central : *(ecran 0x25 + 0x1b84) ---------------------------
    ; Releve dans le jeu : 0x02fbcaf8, methode de l'ecran 0x25, fait
    ; `lwz r3, 0x1b84(r3)` avant de sauter dans 0x02ed1f7c -- l'empilement.
    ; L'objet obtenu porte bien la liste en +0x14c et son compte en +0x154.
    lwz   r12, apScrTable@l(r11)
    lwz   r12, 0x94(r12)            ; 0x25 * 4
    cmpwi r12, 0
    beq   apResolveDlg
    lwz   r12, 0x1b84(r12)
    cmpwi r12, 0
    beq   apResolveDlg
    stw   r12, apMS1This@l(r11)
    stw   r12, apPushThis@l(r11)

apResolveDlg:
    ; --- boite de dialogue : ecran 0x26 -------------------------------------
    ; L'emplacement est VIDE la plupart du temps : 0x035ff8fc cree l'ecran
    ; lui-meme (`li r3, 0x26 ; bl 0x033924c4`) et le detruit a la fermeture.
    ; On ne peut donc pas conditionner l'ouverture a ce pointeur -- seulement
    ; le tenir a jour pour le bloc qui ecrit le texte, dans la meme image.
    lwz   r12, apScrTable@l(r11)
    lwz   r12, 0x98(r12)            ; 0x26 * 4
    cmpwi r12, 0
    beq   apResolveDur
    stw   r12, apDlgThis@l(r11)

apResolveDur:
    ; --- duree de la notification -------------------------------------------
    ; La sonde la relevait sur un vrai ramassage (f31 dans 0x02ffaaec) ; a
    ; froid elle valait 0, et une duree nulle ne montre rien. On reprend la
    ; constante que le jeu se passe a lui-meme, 0x1024C1FC = 5.0f.
    lwz   r12, apDuration@l(r11)
    cmpwi r12, 0
    bne   apResolveDone
    lis   r12, 0x1024
    ori   r12, r12, 0xc1fc
    lwz   r12, 0(r12)
    stw   r12, apDuration@l(r11)

apResolveDone:
    lwz   r12, apResolveN@l(r11)
    addi  r12, r12, 1
    stw   r12, apResolveN@l(r11)

    ; --- soupape : le blocage des objets accordes s'eteint tout seul ---------
    ; apBlockGrants est un COMPTE D'IMAGES, pas un booleen. Si le client Python
    ; meurt en laissant le blocage arme, le champ n'est plus rafraichi et le
    ; jeu redevient normal de lui-meme. Sans ca, les coffres resteraient muets
    ; sans que rien ne l'explique -- et le champ survit au rechargement d'une
    ; sauvegarde, donc le joueur n'aurait aucun moyen simple de s'en sortir.
    lwz   r12, apBlockGrants@l(r11)
    cmpwi r12, 0
    beq   apNoDecay
    addi  r12, r12, -1
    stw   r12, apBlockGrants@l(r11)
apNoDecay:

    ; --- boite aux lettres d'echo (test de liaison) -------------------------
    lwz   r12, apInbox@l(r11)
    cmpwi r12, 0
    beq   apCheckRune
    stw   r12, apOutbox@l(r11)
    stw   r12, apLastSeen@l(r11)
    li    r12, 0
    stw   r12, apInbox@l(r11)

apCheckRune:
    ; --- appeler nous-memes le compteur de runes du jeu ----------------------
    ; FUN_0307B5B0 interroge les cinq predicats et additionne. Le comparer avant
    ; et apres une ecriture de flag dit si le jeu VOIT cette ecriture a chaud.
    lwz   r12, apRuneReq@l(r11)
    cmpwi r12, 0
    beq   apCheckNotify

    li    r12, 0
    stw   r12, apRuneReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    lis   r12, 0x0307
    ori   r12, r12, 0xb5b0          ; FUN_0307B5B0, compteur de runes
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    stw   r3, apRuneCount@l(r11)    ; le compte revient dans r3

    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apRuneDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apRuneDone@l(r11)

apCheckNotify:
    ; --- demander l'affichage de la notification d'objet obtenu -------------
    ; Appelle FUN_02FFA888(ecran PickUpWin, SafeString* nom), identifiee par
    ; sondage : seule fonction de la zone declenchee une fois par ramassage.
    lwz   r12, apNotifyReq@l(r11)
    cmpwi r12, 0
    beq   apCheckPlay           ; et non apCheckGive : sauter la
                                ; ferait passer par-dessus le bloc
                                ; du message central a chaque image
                                ; ou aucune notification n'attend

    li    r12, 0
    stw   r12, apNotifyReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    lis   r12, apItemName@ha
    addi  r12, r12, apItemName@l
    stw   r12, apNameCstr@l(r11)
    lis   r12, 0x1026
    ori   r12, r12, 0x3910
    stw   r12, apNameVtable@l(r11)

    ; --- OUVRIR l'ecran avant de remplir une ligne ---------------------------
    ; Etape manquante, trouvee en resolvant l'ecran statiquement : la ligne se
    ; remplissait bien (rang 0 pose, pool coherent) mais RIEN ne s'affichait,
    ; parce que l'ecran 0x28 restait ferme -- octet d'activite 0xff dans
    ; gestionnaire+0x604. Elle ne se voyait pas tant qu'un vrai ramassage
    ; devait preceder : c'est LUI qui ouvrait l'ecran.
    ; On ne rejoue pas le dispatch : 0x02FFABFC(ecran, _, 0) est justement la
    ; fonction du jeu qui n'appelle que vtable[0x2c](ecran, 3), l'ouverture,
    ; et s'arrete la quand son 3e argument est nul.
    lwz   r3, apScreenThis@l(r11)
    cmpwi r3, 0
    beq   apNotifyEnd               ; ecran non resolu : ne rien tenter
    li    r4, 0
    li    r5, 0
    lis   r12, 0x02FF
    ori   r12, r12, 0xabfc
    mtctr r12
    bctrl

    lis   r11, apTick@ha            ; r11 a ete detruit par l'appel

    ; --- choisir une ligne LIBRE dans le pool -------------------------------
    ; C'est ce que fait la fonction englobante et que nous ne faisions pas :
    ; on reutilisait toujours la meme ligne, d'ou le remplacement au lieu de
    ; l'empilement. On refait sa boucle sans l'appeler, car son premier argument
    ; est l'ecran -- un objet transitoire dont le pointeur capture finit par
    ; danglinguer, ce qui a fait planter le jeu.
    ;   liste->0x3c = nombre de lignes
    ;   liste->0x44 = tableau de pointeurs
    ;   0x02FFA5E0(ligne) renvoie 0 si la ligne est libre
    ; L'etat de boucle vit dans le cave : l'appel au predicat detruit r3-r12.

    lwz   r12, apListThis@l(r11)
    cmpwi r12, 0
    beq   apNotifyEnd

    lwz   r10, 0x44(r12)
    stw   r10, apIterPtr@l(r11)
    lwz   r10, 0x3c(r12)
    stw   r10, apIterLeft@l(r11)

apFindLoop:
    lis   r11, apTick@ha
    lwz   r12, apIterLeft@l(r11)
    cmpwi r12, 0
    beq   apNotifyEnd               ; aucune ligne libre : ne rien afficher
    addi  r12, r12, -1
    stw   r12, apIterLeft@l(r11)

    lwz   r12, apIterPtr@l(r11)
    lwz   r3, 0(r12)
    addi  r12, r12, 4
    stw   r12, apIterPtr@l(r11)

    cmpwi r3, 0
    beq   apFindLoop

    stw   r3, apCandidate@l(r11)
    lis   r12, 0x02FF
    ori   r12, r12, 0xa5e0
    mtctr r12
    bctrl

    cmpwi r3, 0
    bne   apFindLoop                ; occupee : ligne suivante

    ; --- faire descendre les lignes deja affichees ---------------------------
    ; Seconde boucle de l'appelant, tout aussi indispensable : sans elle les
    ; entrees existantes ne descendent pas d'un cran et la nouvelle se superpose.
    ; L'octet a ligne+0x149 est le rang ; il est incremente sur chaque ligne
    ; OCCUPEE (predicat non nul).
    lwz   r12, apListThis@l(r11)
    lwz   r10, 0x44(r12)
    stw   r10, apIterPtr@l(r11)
    lwz   r10, 0x3c(r12)
    stw   r10, apIterLeft@l(r11)

apAgeLoop:
    lis   r11, apTick@ha
    lwz   r12, apIterLeft@l(r11)
    cmpwi r12, 0
    beq   apAgeDone
    addi  r12, r12, -1
    stw   r12, apIterLeft@l(r11)

    lwz   r12, apIterPtr@l(r11)
    lwz   r3, 0(r12)
    addi  r12, r12, 4
    stw   r12, apIterPtr@l(r11)

    cmpwi r3, 0
    beq   apAgeLoop

    stw   r3, apCandidate2@l(r11)
    lis   r12, 0x02FF
    ori   r12, r12, 0xa5e0
    mtctr r12
    bctrl

    cmpwi r3, 0
    beq   apAgeLoop                 ; ligne libre : rien a decaler

    lis   r11, apTick@ha
    lwz   r12, apCandidate2@l(r11)
    lbz   r10, 0x149(r12)
    addi  r10, r10, 1
    stb   r10, 0x149(r12)
    b     apAgeLoop

apAgeDone:
    ; --- ligne libre trouvee : preparer, remplir, afficher -------------------
    lis   r11, apTick@ha
    stfs  f1, apSaveF1@l(r11)
    lfs   f1, apDuration@l(r11)     ; la duree que le jeu emploie lui-meme
    lwz   r3, apCandidate@l(r11)
    lis   r12, 0x02FF
    ori   r12, r12, 0xa5f4
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r3, apCandidate@l(r11)
    lis   r4, apNameCstr@ha
    addi  r4, r4, apNameCstr@l
    lis   r12, 0x02FF
    ori   r12, r12, 0xa888
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r3, apCandidate@l(r11)
    lis   r12, 0x02FF
    ori   r12, r12, 0xaa34
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lfs   f1, apSaveF1@l(r11)

apNotifyEnd:
    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apNotifyDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apNotifyDone@l(r11)

apCheckPlay:
    ; --- rejouer l'empilement du jeu ----------------------------------------
    ; 0x02ed1f7c(this, a, b) incremente le compteur de la liste this+0x154 ;
    ; c'est l'etape qui manquait, et sans elle 0x02ed1e1c sort par `ble` des
    ; l'entree. Les arguments ne sont pas devines : l'espion apPushSpy les
    ; releve quand le JEU affiche un message, et on les rejoue tels quels.
    lwz   r12, apPlayReq@l(r11)
    cmpwi r12, 0
    beq   apCheckMsg

    lwz   r12, apPushThis@l(r11)
    cmpwi r12, 0
    beq   apCheckMsg               ; jamais vu : ne rien tenter

    li    r12, 0
    stw   r12, apPlayReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; Le 3e argument est un POINTEUR : 0x02ed1f7c dereference 0x0(r5) et
    ; 0x4(r5), la disposition d'un sead::SafeString {cstr, vtable}. C'est le
    ; texte substitue dans le message -- le "Spear"/"Sword" vu a this+0x17c.
    ; Rejouer le pointeur releve sur le jeu le fait pointer sur une pile morte,
    ; d'ou le plantage. On construit donc le notre, sur apText.
    lis   r12, apText@ha
    addi  r12, r12, apText@l
    stw   r12, apMsgCstr@l(r11)
    lis   r12, 0x1026
    ori   r12, r12, 0x3910          ; vtable de sead::SafeString
    stw   r12, apMsgVtable@l(r11)

    lwz   r3, apPushThis@l(r11)
    lwz   r4, apPlayA@l(r11)
    lwz   r12, apPlayRaw@l(r11)
    cmpwi r12, 0
    beq   apPlayOwn
    lwz   r5, apPlayB@l(r11)        ; --raw : rejouer le pointeur du jeu
    b     apPlayCall
apPlayOwn:
    lis   r5, apMsgCstr@ha
    addi  r5, r5, apMsgCstr@l
apPlayCall:
    lis   r12, 0x02ed
    ori   r12, r12, 0x1f7c
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apPlayDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apPlayDone@l(r11)

apCheckMsg:
    ; --- declencher le message central --------------------------------------
    ; 0x02ed1e1c(this, arg) : API publique qui empile la demande puis appelle
    ; elle-meme 0x02ed1a68, laquelle va chercher le label dans MainScreen_00.
    ; 0x02ed1a68 avait ete trouvee par sondage (2 appels contre 602 pour les
    ; fonctions per-frame) ; son appelant, en cherchant qui calcule this+0x14c.
    lwz   r12, apMSReq@l(r11)
    cmpwi r12, 0
    beq   apCheckTips           ; bloc SUIVANT, pas le dernier : sauter
                                ; directement a apCheckGive rendrait tout
                                ; le bloc des conseils inatteignable

    lwz   r12, apMS1This@l(r11)
    cmpwi r12, 0
    beq   apCheckTips               ; jamais vue : ne rien tenter

    li    r12, 0
    stw   r12, apMSReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; --- appeler l'API PUBLIQUE, et non la fonction d'affichage --------------
    ; 0x02ed1e1c(this, arg) empile la demande via 0x036028e0 puis appelle
    ; lui-meme 0x02ed1a68. C'est ce qui manquait : poser index et etat a la main
    ; ne declenchait rien, parce que l'empilement dans la liste this+0x14c
    ; n'avait pas eu lieu. Trouvee en cherchant qui calcule l'adresse de cette
    ; liste : deux sites seulement, hors consommateur.
    ; r4 n'est PAS l'index : 0x036028e0 fait seulement `cmpwi r4, 0` pour
    ; choisir entre deux etats (1 ou 3) ecrits dans this+0x8c. L'index, lui,
    ; vient de this+0xbc -- le champ dont on sait deja qu'il pilote le contenu.
    lwz   r3, apMS1This@l(r11)
    lwz   r12, apMSIndex@l(r11)
    stw   r12, 0xbc(r3)

    ; --- relever ce que la fonction va tester, DANS LA MEME FRAME ------------
    ; Lire ces champs depuis Python donne l'etat d'une frame anterieure, et
    ; trois deductions faites sur le desassemblage ont deja ete contredites.
    lwz   r12, 0x154(r3)
    stw   r12, apMSDbg154@l(r11)
    lwz   r12, 0x150(r3)
    stw   r12, apMSDbg150@l(r11)
    lwz   r12, 0x8c(r3)
    stw   r12, apMSDbgC@l(r11)

    lwz   r4, apMSFlag@l(r11)
    lis   r12, 0x02ed
    ori   r12, r12, 0x1e1c
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    stw   r3, apMSRet@l(r11)        ; valeur de retour, 0 = refuse

apMsgRestored:
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apMSDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apMSDone@l(r11)

apCheckTips:
    ; --- afficher le cadre bleu des conseils --------------------------------
    ; 0x02fd4848(this, index) va chercher le libelle numero `index` dans la
    ; table de 23 entrees de 0x10542f7c, resout le message dans
    ; LayoutMsg/MessageTipsRunTime_00, le pose sur le pane T_Text_00 puis joue
    ; l'animation d'apparition. Le `this` n'est pas cherche : la sonde
    ; apTipsProbe1 le capture sur la mise a jour par image.
    lwz   r12, apTipsReq@l(r11)
    cmpwi r12, 0
    beq   apCheckTipsText

    lwz   r12, apTipsThis@l(r11)
    cmpwi r12, 0
    beq   apCheckTipsText           ; jamais vu : ne rien tenter

    li    r12, 0
    stw   r12, apTipsReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    lwz   r3, apTipsThis@l(r11)
    lwz   r4, apTipsIndex@l(r11)
    lis   r12, 0x02fd
    ori   r12, r12, 0x4848
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apTipsDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apTipsDone@l(r11)

apCheckTipsText:
    ; --- ecrire NOTRE texte dans le cadre -----------------------------------
    ; 0x03082d88(layout, sead::SafeString* nomDePane, objetTexte) est l'appel
    ; que 0x02fd4848 fait lui-meme juste apres avoir resolu le message. Rejoue
    ; ici avec notre propre objet texte, il remplace le contenu du pane sans
    ; toucher a l'arene des messages -- donc sans plafond herite du porteur et
    ; sans restauration a faire.
    ; L'objet texte fait huit octets { const char16_t* ; longueur } : c'est ce
    ; que 0x03082c70 recopie dans le tampon de 0x02fd4848 (0x03a38d9c ne
    ; transfere que deux mots). apTipsSpy releve le couple que le jeu emploie.
    lwz   r12, apTipsTextReq@l(r11)
    cmpwi r12, 0
    beq   apCheckDlg

    lwz   r12, apTipsThis@l(r11)
    cmpwi r12, 0
    beq   apCheckDlg               ; jamais vu : ne rien tenter

    li    r12, 0
    stw   r12, apTipsTextReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; sead::SafeString sur 'T_Text_00' (0x1024609c), la chaine du jeu elle-meme
    lis   r12, 0x1024
    ori   r12, r12, 0x609c
    stw   r12, apPaneCstr@l(r11)
    lis   r12, 0x1026
    ori   r12, r12, 0x3910
    stw   r12, apPaneVtable@l(r11)

    ; objet texte : apText, en UTF-16BE, et la longueur posee par Python
    lis   r12, apText@ha
    addi  r12, r12, apText@l
    stw   r12, apTipsStrPtr@l(r11)
    lwz   r12, apTipsTextLen@l(r11)
    stw   r12, apTipsStrLen@l(r11)

    lwz   r3, apTipsThis@l(r11)
    lwz   r3, 0x18(r3)              ; le layout du widget
    lis   r4, apPaneCstr@ha
    addi  r4, r4, apPaneCstr@l
    lis   r5, apTipsStrPtr@ha
    addi  r5, r5, apTipsStrPtr@l
    lis   r12, 0x0308
    ori   r12, r12, 0x2d88
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apTipsTextDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apTipsTextDone@l(r11)

apCheckDlg:
    ; --- ouvrir la fenetre de dialogue sur un couple (archive, libelle) -----
    lwz   r12, apDlgReq@l(r11)
    cmpwi r12, 0
    beq   apCheckDlgText

    ; --- le seul vrai prerequis : que l'IHM existe --------------------------
    ; Le verrou etait apDlgOpen0N (« aucune vraie boite vue depuis le
    ; lancement »), et il ne protegeait rien : les trois arguments rejoues
    ; sont forces a zero de toute facon, parce que 0x035ff8fc ne les relit
    ; que sur la branche a drapeau non nul. Ce qu'il faut vraiment, c'est que
    ; *(0x1047E650) existe : la fonction le dereference sans le tester.
    ; L'ecran 0x26, lui, n'a pas a exister -- elle le cree elle-meme.
    lwz   r12, apScrTable@l(r11)
    cmpwi r12, 0
    beq   apCheckDlgText            ; IHM pas prete : ne rien tenter

    li    r12, 0
    stw   r12, apDlgReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    lis   r12, apArcBuf@ha
    addi  r12, r12, apArcBuf@l
    stw   r12, apDlgArcCstr@l(r11)
    lis   r12, 0x1026
    ori   r12, r12, 0x3910
    stw   r12, apDlgArcVtable@l(r11)
    lis   r12, apLblBuf@ha
    addi  r12, r12, apLblBuf@l
    stw   r12, apDlgLblCstr@l(r11)
    lis   r12, 0x1026
    ori   r12, r12, 0x3910
    stw   r12, apDlgLblVtable@l(r11)

    li    r3, 0                     ; ignore par la fonction
    lis   r4, apDlgArcCstr@ha
    addi  r4, r4, apDlgArcCstr@l
    lis   r5, apDlgLblCstr@ha
    addi  r5, r5, apDlgLblCstr@l
    lwz   r6, apDlgArg6@l(r11)      ; releves sur un vrai appel
    lwz   r7, apDlgArg7@l(r11)
    lwz   r8, apDlgArg8@l(r11)
    lis   r12, 0x035f
    ori   r12, r12, 0xf8fc
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apDlgDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apDlgDone@l(r11)

apCheckDlgText:
    ; --- substituer NOTRE texte a celui que la fenetre vient de resoudre ----
    ; 0x035fb5f8 range { texte, longueur } dans this+0x1d0 ; on ecrit le
    ; notre par-dessus. Aucun appel : deux ecritures, dans la meme image que
    ; l'ouverture puisque les deux blocs se suivent.
    ; La longueur est en UNITES UTF-16, terminateur exclu -- mesure sur le
    ; cadre des conseils : porteur de 101 unites, mot1 releve = 100.
    lwz   r12, apDlgTextReq@l(r11)
    cmpwi r12, 0
    beq   apCheckGetWin             ; bloc SUIVANT, pas le dernier

    lwz   r12, apDlgThis@l(r11)
    cmpwi r12, 0
    beq   apCheckGetWin             ; jamais vue : ne rien tenter

    li    r12, 0
    stw   r12, apDlgTextReq@l(r11)

    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    lwz   r3, apDlgThis@l(r11)
    lwz   r4, apDlgStrPtr@l(r11)
    stw   r4, 0x1d0(r3)
    lwz   r4, apDlgStrLen@l(r11)
    stw   r4, 0x1d4(r3)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)

    lwz   r12, apDlgTextDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apDlgTextDone@l(r11)

apCheckGetWin:
    ; --- rejouer la fenetre d'obtention avec notre propre texte ------------
    ; On rappelle le pilote 0x03a3ec0c avec les arguments releves sur un vrai
    ; declenchement, sauf r6 : a la place du `const char*` du jeu, le notre.
    ; Meme principe que le rejeu de la boite de dialogue -- on ne recree pas
    ; la mise en scene, on redemande celle du jeu avec un texte substitue.
    lwz   r12, apGetDrvReq@l(r11)
    cmpwi r12, 0
    beq   apCheckGive

    lwz   r12, apGetWinOk@l(r11)
    cmpwi r12, 0
    beq   apCheckGive               ; MessageGet_00 jamais vu s'ouvrir : les
                                    ; arguments a rejouer ne sont pas connus

    li    r12, 0
    stw   r12, apGetDrvReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; r6 reste le nom d'ecran du jeu. Y mettre notre texte a plante : cette
    ; fonction ouvre un ecran PAR SON NOM, elle n'affiche rien elle-meme.
    lwz   r3, apGetWinCThis@l(r11)
    lwz   r4, apGetWinCA4@l(r11)
    lwz   r5, apGetWinCA5@l(r11)
    lwz   r6, apGetWinCA6@l(r11)
    lwz   r7, apGetWinCA7@l(r11)
    lwz   r8, apGetWinCA8@l(r11)
    lwz   r9, apGetWinCA9@l(r11)
    lis   r12, 0x03a3
    ori   r12, r12, 0xec0c
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apGetDrvDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetDrvDone@l(r11)

apCheckGive:
    lwz   r12, apGiveReq@l(r11)
    cmpwi r12, 0
    beq   apCheckCall

    lwz   r12, apPmdmThis@l(r11)    ; a-t-on deja capture le this ?
    cmpwi r12, 0
    beq   apCheckCall

    li    r12, 0                    ; consommer AVANT d'appeler, pour ne pas
    stw   r12, apGiveReq@l(r11)     ; boucler indefiniment si itemGet plante

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; construire le sead::SafeString a la volee
    lis   r12, apItemName@ha
    addi  r12, r12, apItemName@l
    stw   r12, apNameCstr@l(r11)
    lis   r12, 0x1026
    ori   r12, r12, 0x3910          ; vtable de sead::SafeString
    stw   r12, apNameVtable@l(r11)

    lwz   r3, apPmdmThis@l(r11)     ; this
    lis   r4, apNameCstr@ha
    addi  r4, r4, apNameCstr@l      ; const sead::SafeString&
    lwz   r5, apGiveValue@l(r11)    ; quantite
    li    r6, 0                     ; pas de modificateur d'arme

    ; --- appel indirect, et non "bla" -------------------------------------
    ; bla n'a qu'un deplacement signe sur 26 bits, soit +/-32 Mo. itemGet est a
    ; 0x02EB53E4, au-dela de 0x01FFFFFC : le bit de signe est mis et l'adresse
    ; devient 0xFEEB53E4. C'est exactement ce qui a plante le jeu.
    ; ori plutot qu'addi pour la moitie basse : addi l'interprete comme signee.
    lis   r12, 0x02EB
    ori   r12, r12, 0x53E4          ; itemGet
    mtctr r12
    bctrl

    lis   r11, apTick@ha            ; r11 a ete detruit par l'appel
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apGiveDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apGiveDone@l(r11)

apCheckCall:
    ; --- appeler n'importe quoi, depuis le hook per-frame ------------------
    ; Meme protocole que apOpnMode 8, mais sans verrou : ce hook tourne a
    ; chaque image depuis le demarrage du jeu.
    ; PRUDENCE : le patch documente une affinite de thread pour le REJEU du
    ; site d'ouverture (pile 0x12b3c510 contre 0x0e201270 ici) -- quatre
    ; plantages. Elle vaut pour les modes qui touchent l'interieur d'un ecran ;
    ; pour un appel propre comme 0x035fe7f4 elle reste a mesurer.
    lwz   r12, apPfReq@l(r11)
    cmpwi r12, 0
    beq   apDone

    li    r12, 0                    ; consommer AVANT d'appeler, pour ne pas
    stw   r12, apPfReq@l(r11)       ; boucler indefiniment si l'appel plante

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    lwz   r12, apCallAddr@l(r11)
    mtctr r12
    lwz   r3, apCallA1@l(r11)
    lwz   r4, apCallA2@l(r11)
    lwz   r5, apCallA3@l(r11)
    lwz   r6, apCallA4@l(r11)
    lwz   r7, apCallA5@l(r11)
    lwz   r8, apCallA6@l(r11)
    lwz   r9, apCallA7@l(r11)
    lwz   r10, apCallA8@l(r11)
    bctrl

    lis   r11, apTick@ha            ; r11 a ete detruit par l'appel
    stw   r3, apCallRet@l(r11)
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apCallN@l(r11)
    addi  r12, r12, 1
    stw   r12, apCallN@l(r11)

apDone:
    blr

apItemGetSpy:
    stw   r0, 0x6c(r1)          ; --- ORIGINE hook 2, rejouee en premier ---
                                ; c'est elle qui sauve LR pour l'epilogue :
                                ; la rejouer AVANT de sauter la-bas est ce qui
                                ; rend le court-circuit sur.

    lis   r11, apTick@ha
    lwz   r12, apItemGetCount@l(r11)
    addi  r12, r12, 1
    stw   r12, apItemGetCount@l(r11)
    stw   r24, apPmdmThis@l(r11)      ; this de PauseMenuDataMgr
    stw   r25, apLastNamePtr@l(r11)   ; SafeString* du nom
    stw   r26, apLastValue@l(r11)     ; quantite

    ; --- journal : { site d'appel, cstr du nom, quantite } ------------------
    ; r11 est sacrifie pour lire *(r25) puis rechargee : c'est la seule facon
    ; de tenir trois valeurs avec deux registres de travail, sans supposer que
    ; r0 est mort -- supposition jamais verifiee, donc jamais faite.
    lwz   r12, apIgLeft@l(r11)
    cmpwi r12, 0
    beq   apIgBlock
    addi  r12, r12, -1
    stw   r12, apIgLeft@l(r11)
    lwz   r12, apIgPtr@l(r11)
    stw   r0, 0x0(r12)                ; adresse de retour = site d'appel
    stw   r26, 0x8(r12)               ; quantite
    lwz   r11, 0x0(r25)               ; cstr du nom
    stw   r11, 0x4(r12)
    lis   r11, apTick@ha              ; recharger la base du cave
    addi  r12, r12, 12
    stw   r12, apIgPtr@l(r11)

apIgBlock:
    ; --- court-circuit : sortir sans rien ajouter ---------------------------
    ; Deux commandes independantes :
    ;   apBlockReq    neutralise le PROCHAIN objet, quelle qu'en soit la source
    ;   apBlockGrants neutralise seulement Obj_DungeonClearSeal, reconnu au
    ;                 marqueur pose par apGrantSpy puis au SafeString de r25.
    lwz   r12, apBlockReq@l(r11)
    cmpwi r12, 0
    bne   apIgDoBlock

    lwz   r12, apBlockGrants@l(r11)
    cmpwi r12, 0
    beq   apIgClearMark
    lwz   r12, apGrantMark@l(r11)
    cmpwi r12, 0
    beq   apIgClearMark

    ; FILTRE SELECTIF, mesure au site itemGet : r25 est le SafeString du nom,
    ; et *(r25) sa cstr ASCII. Comparaison octet par octet : l'assembleur de
    ; Cemu accepte lbz/cmpwi, tandis que cmpw/cmplw n'ont pas ete valides.
    ; Un mismatch recharge la base du cave avant de suivre le chemin normal.
    lwz   r12, 0x0(r25)
    lbz   r11, 0x00(r12)
    cmpwi r11, 0x4f                    ; O
    bne   apIgNotDungeonSeal
    lbz   r11, 0x01(r12)
    cmpwi r11, 0x62                    ; b
    bne   apIgNotDungeonSeal
    lbz   r11, 0x02(r12)
    cmpwi r11, 0x6a                    ; j
    bne   apIgNotDungeonSeal
    lbz   r11, 0x03(r12)
    cmpwi r11, 0x5f                    ; _
    bne   apIgNotDungeonSeal
    lbz   r11, 0x04(r12)
    cmpwi r11, 0x44                    ; D
    bne   apIgNotDungeonSeal
    lbz   r11, 0x05(r12)
    cmpwi r11, 0x75                    ; u
    bne   apIgNotDungeonSeal
    lbz   r11, 0x06(r12)
    cmpwi r11, 0x6e                    ; n
    bne   apIgNotDungeonSeal
    lbz   r11, 0x07(r12)
    cmpwi r11, 0x67                    ; g
    bne   apIgNotDungeonSeal
    lbz   r11, 0x08(r12)
    cmpwi r11, 0x65                    ; e
    bne   apIgNotDungeonSeal
    lbz   r11, 0x09(r12)
    cmpwi r11, 0x6f                    ; o
    bne   apIgNotDungeonSeal
    lbz   r11, 0x0a(r12)
    cmpwi r11, 0x6e                    ; n
    bne   apIgNotDungeonSeal
    lbz   r11, 0x0b(r12)
    cmpwi r11, 0x43                    ; C
    bne   apIgNotDungeonSeal
    lbz   r11, 0x0c(r12)
    cmpwi r11, 0x6c                    ; l
    bne   apIgNotDungeonSeal
    lbz   r11, 0x0d(r12)
    cmpwi r11, 0x65                    ; e
    bne   apIgNotDungeonSeal
    lbz   r11, 0x0e(r12)
    cmpwi r11, 0x61                    ; a
    bne   apIgNotDungeonSeal
    lbz   r11, 0x0f(r12)
    cmpwi r11, 0x72                    ; r
    bne   apIgNotDungeonSeal
    lbz   r11, 0x10(r12)
    cmpwi r11, 0x53                    ; S
    bne   apIgNotDungeonSeal
    lbz   r11, 0x11(r12)
    cmpwi r11, 0x65                    ; e
    bne   apIgNotDungeonSeal
    lbz   r11, 0x12(r12)
    cmpwi r11, 0x61                    ; a
    bne   apIgNotDungeonSeal
    lbz   r11, 0x13(r12)
    cmpwi r11, 0x6c                    ; l
    bne   apIgNotDungeonSeal
    lbz   r11, 0x14(r12)
    cmpwi r11, 0x00                    ; terminateur
    bne   apIgNotDungeonSeal
    lis   r11, apTick@ha
    b     apIgDoBlock

apIgNotDungeonSeal:
    lis   r11, apTick@ha
    b     apIgClearMark

apIgDoBlock:

    li    r12, 0                      ; consommer AVANT de sauter
    stw   r12, apBlockReq@l(r11)
    lwz   r12, apBlockDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apBlockDone@l(r11)

    li    r12, 0                      ; le marqueur ne doit pas resservir
    stw   r12, apGrantMark@l(r11)

    lis   r12, 0x02eb
    ori   r12, r12, 0x5894            ; epilogue de itemGet
    mtlr  r12
    blr                               ; -> lmw / mtlr / addi r1 / blr

apIgClearMark:
    li    r12, 0                      ; consommer le marqueur meme sans blocage,
    stw   r12, apGrantMark@l(r11)     ; sinon il deborde sur le ramassage suivant
    blr

; --- sonde de capture sur 0x02FFAAF0, la fonction complete de notification ---
; Placee a 0x02FFAB18, apres le stw r0,0x2c(r1) qui sauve LR : hooker plus tot
; detruirait l'adresse de retour. A ce point r3 est encore l'ecran, et f31
; contient deja l'argument flottant (fmr f31,f1 a 0x02FFAB04).
apProbeScreen:
    addi  r29, r3, 0x1b68           ; origine
    lis   r11, apTick@ha
    stw   r3, apScreenThis@l(r11)   ; l'ecran, pas une ligne du pool
    stw   r29, apListThis@l(r11)    ; ecran + 0x1b68 : le pool de lignes
    stfs  f31, apDuration@l(r11)    ; la duree que le jeu se donne a lui-meme
    blr


apMSProbe0:                      ; fonction 0x02ecbca4
    lwz   r3, 0xc(r27)          ; origine
    lis   r11, apTick@ha
    stw   r27, apMSThis@l(r11)   ; le 'this' d'origine
    lwz   r12, apMSMask@l(r11)
    ori   r12, r12, 0x0001
    stw   r12, apMSMask@l(r11)
    lwz   r12, apMS0@l(r11)
    addi  r12, r12, 1
    stw   r12, apMS0@l(r11)
    blr

apMSProbe1:                      ; fonction 0x02ed1a68
    lwz   r5, 0x154(r28)          ; origine
    lis   r11, apTick@ha
    stw   r28, apMS1This@l(r11)  ; champ dedie : apMSThis est
                                ; ecrase par MS5, qui tourne
                                ; a chaque image
    lwz   r12, apMSMask@l(r11)
    ori   r12, r12, 0x0002
    stw   r12, apMSMask@l(r11)
    lwz   r12, apMS1@l(r11)
    addi  r12, r12, 1
    stw   r12, apMS1@l(r11)
    blr

apMSProbe2:                      ; fonction 0x02f21984
    ; Ancree sur le stw qui sauve LR, et NON sur le lis suivant :
    ; celui-ci charge r12, que 0x02f2199c relit deux instructions
    ; plus loin. La sonde se sert de r12 comme registre de travail,
    ; elle l'aurait donc detruit -- ce qui plantait le jeu au lancement.
    stw   r0, 0x5c(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apMSMask@l(r11)
    ori   r12, r12, 0x0004
    stw   r12, apMSMask@l(r11)
    lwz   r12, apMS2@l(r11)
    addi  r12, r12, 1
    stw   r12, apMS2@l(r11)
    blr

apMSProbe3:                      ; fonction 0x02f8b2bc
    addi  r3, r1, 0x40          ; origine
    lis   r11, apTick@ha
    stw   r27, apMSThis@l(r11)   ; le 'this' d'origine
    lwz   r12, apMSMask@l(r11)
    ori   r12, r12, 0x0008
    stw   r12, apMSMask@l(r11)
    lwz   r12, apMS3@l(r11)
    addi  r12, r12, 1
    stw   r12, apMS3@l(r11)
    blr

apMSProbe4:                      ; fonction 0x02fc0f58
    stfs  f29, 0x1b8(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apMSMask@l(r11)
    ori   r12, r12, 0x0010
    stw   r12, apMSMask@l(r11)
    lwz   r12, apMS4@l(r11)
    addi  r12, r12, 1
    stw   r12, apMS4@l(r11)
    blr

apMSProbe5:                      ; fonction 0x02fc2dec
    lwz   r8, 0x0(r30)          ; origine
    lis   r11, apTick@ha
    stw   r30, apMSThis@l(r11)   ; le 'this' d'origine
    lwz   r12, apMSMask@l(r11)
    ori   r12, r12, 0x0020
    stw   r12, apMSMask@l(r11)
    lwz   r12, apMS5@l(r11)
    addi  r12, r12, 1
    stw   r12, apMS5@l(r11)
    blr

apMSTraceMid:                    ; 0x02ed1e70, apres les trois premiers tests
    lwz   r0, 0x8c(r29)        ; origine -- r0 n'est PAS touche ensuite,
                               ; les comparaisons qui suivent en dependent
    lis   r11, apTick@ha
    stw   r0, apMSDbg8c@l(r11) ; la valeur que la fonction voit VRAIMENT
    lwz   r12, apMSMid@l(r11)
    addi  r12, r12, 1
    stw   r12, apMSMid@l(r11)
    blr

apPushSpy:                       ; 0x02ed1f98, dans 0x02ed1f7c
    addi  r27, r24, 0x110      ; origine
    lis   r11, apTick@ha
    stw   r24, apPushThis@l(r11)   ; this
    stw   r29, apPushA@l(r11)      ; 2e argument
    stw   r30, apPushB@l(r11)      ; 3e argument
    lwz   r12, apPushN@l(r11)
    addi  r12, r12, 1
    stw   r12, apPushN@l(r11)
    blr

apMSTracePass:                   ; 0x02ed1e98, juste avant bl 0x036028e0
    mr    r3, r29              ; origine
    lis   r11, apTick@ha
    lwz   r12, apMSPass@l(r11)
    addi  r12, r12, 1
    stw   r12, apMSPass@l(r11)
    blr

apMSTraceBail:                   ; 0x02ed1e5c, chemin de sortie anticipee
    lwz   r0, 0x24(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apMSBail@l(r11)
    addi  r12, r12, 1
    stw   r12, apMSBail@l(r11)
    blr

; --- sondes du cadre bleu des conseils --------------------------------
; Module 0x02fd3c74-0x02fd5340, celui qui reference
; LayoutMsg/MessageTipsRunTime_00. Chaque sonde rejoue son instruction
; d'origine -- toujours le `stw r0, N(r1)` qui sauve LR, ou r11 et r12
; sont morts -- allume son bit et incremente son compteur.

apTipsProbe0:                    ; 0x02fd4848, affichage d'un conseil
    stw   r0, 0x2c(r1)          ; origine
    lis   r11, apTick@ha
    stw   r30, apTipsShowThis@l(r11)   ; this
    stw   r31, apTipsShowIdx@l(r11)    ; l'index demande
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0001
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips0@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips0@l(r11)
    blr

apTipsProbe1:                    ; 0x02fd4a1c, mise a jour par image
    stw   r0, 0x14(r1)          ; origine
    lis   r11, apTick@ha
    stw   r31, apTipsThis@l(r11)       ; champ dedie : c'est CE this qu'on
                                       ; rejouera, celui de l'objet persistant
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0002
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips1@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips1@l(r11)
    blr

apTipsProbe2:                    ; 0x02fd3c74, construction du layout
    stw   r0, 0x84(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0004
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips2@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips2@l(r11)
    blr

apTipsProbe3:                    ; 0x02fd4bc0
    stw   r0, 0x14(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0008
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips3@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips3@l(r11)
    blr

apTipsProbe4:                    ; 0x02fd4730
    stw   r0, 0x1c(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0010
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips4@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips4@l(r11)
    blr

apTipsProbe5:                    ; 0x02fd45ac
    stw   r0, 0x2c(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0020
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips5@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips5@l(r11)
    blr

apTipsProbe6:                    ; 0x02fd4b6c, anime 'GuideOn'
    stw   r0, 0x14(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0040
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips6@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips6@l(r11)
    blr

apTipsProbe7:                    ; 0x02fd46ec
    stw   r0, 0x14(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0080
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips7@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips7@l(r11)
    blr

apTipsSpy:                       ; 0x02fd48c8, juste avant bl 0x03082d88
    ; A ce point r5 pointe sur l'objet texte que le jeu vient de remplir.
    ; On le releve au lieu de deduire ce que valent ses deux mots : c'est
    ; exactement la question que le rejeu doit trancher.
    stw   r0, 0x8(r1)           ; origine
    lis   r11, apTick@ha
    lwz   r12, 0x0(r5)
    stw   r12, apTipsSpyPtr@l(r11)
    lwz   r12, 0x4(r5)
    stw   r12, apTipsSpyLen@l(r11)
    blr

0x02fd4864 = bla apTipsProbe0
0x02fd4a30 = bla apTipsProbe1
0x02fd3c88 = bla apTipsProbe2
0x02fd4bd4 = bla apTipsProbe3
0x02fd4750 = bla apTipsProbe4
0x02fd45d0 = bla apTipsProbe5
0x02fd4b7c = bla apTipsProbe6
0x02fd46f8 = bla apTipsProbe7
0x02fd48c8 = bla apTipsSpy

apMsgSpy:                        ; 0x03a38af0, resolveur de libelle
    stw   r0, 0x1c(r1)          ; origine -- r0 est encore l'adresse de retour
    lis   r11, apTick@ha
    lwz   r12, apRingLeft@l(r11)
    cmpwi r12, 0
    beq   apMsgSpyEnd
    addi  r12, r12, -1
    stw   r12, apRingLeft@l(r11)
    lwz   r12, apRingPtr@l(r11)
    stw   r0, 0x0(r12)          ; d'ou vient la demande
    stw   r5, 0x4(r12)          ; const char* du libelle demande
    addi  r12, r12, 8
    stw   r12, apRingPtr@l(r11)
apMsgSpyEnd:
    blr

0x03a38af0 = bla apMsgSpy
apDlgOpen:                       ; 0x035ff918, dans 0x035ff8fc
    ; Les arguments ne sont releves QUE sur un appel a drapeau nul.
    ; Rejouer un appel a drapeau 1 a plante le jeu : cette branche part dans
    ; 0x035fb1b4, qui DEREFERENCE le 4e et le 5e argument -- deux pointeurs de
    ; tas, morts des l'appel suivant. A drapeau 0 ils ne sont jamais relus
    ; (verifie : r26 et r27 ne reapparaissent qu'en 0x035ffa1c/0x035ffa20).
    stw   r0, 0x34(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apDlgOpenN@l(r11)
    addi  r12, r12, 1
    stw   r12, apDlgOpenN@l(r11)
    cmpwi r28, 0
    bne   apDlgOpenEnd
    stw   r29, apDlgSeenArc@l(r11)  ; SafeString* archive
    stw   r30, apDlgSeenLbl@l(r11)  ; SafeString* libelle
    stw   r26, apDlgArg6@l(r11)     ; 4e argument
    stw   r27, apDlgArg7@l(r11)     ; 5e
    stw   r28, apDlgArg8@l(r11)     ; 6e, le drapeau : nul ici par construction
    lwz   r12, apDlgOpen0N@l(r11)
    addi  r12, r12, 1
    stw   r12, apDlgOpen0N@l(r11)
apDlgOpenEnd:
    blr

apDlgSet:                        ; 0x035fb60c, dans 0x035fb5f8
    stw   r0, 0x34(r1)          ; origine
    lis   r11, apTick@ha
    stw   r27, apDlgThis@l(r11)     ; la fenetre : c'est son +0x1d0 qu'on ecrase
    lwz   r12, apDlgSetN@l(r11)
    addi  r12, r12, 1
    stw   r12, apDlgSetN@l(r11)
    blr

0x035ff918 = bla apDlgOpen
0x035fb60c = bla apDlgSet

apLvlSpy0:                    ; 0x02b77278, dans 0x02b77260
    stw   r0, 0x14(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apLvl0N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl0N@l(r11)
    stw   r3, apLvl0R3@l(r11)
    stw   r4, apLvl0R4@l(r11)
    stw   r5, apLvl0R5@l(r11)
    stw   r6, apLvl0R6@l(r11)
    stw   r7, apLvl0R7@l(r11)
    stw   r0, apLvl0Lr@l(r11)
    blr

0x02b77278 = bla apLvlSpy0

apLvlSpy1:                    ; 0x021c0318, dans 0x021c0308
    stw   r0, 0x1c(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apLvl1N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl1N@l(r11)
    stw   r3, apLvl1R3@l(r11)
    stw   r4, apLvl1R4@l(r11)
    stw   r5, apLvl1R5@l(r11)
    stw   r6, apLvl1R6@l(r11)
    stw   r7, apLvl1R7@l(r11)
    stw   r0, apLvl1Lr@l(r11)
    blr

0x021c0318 = bla apLvlSpy1

apLvlSpy2:                    ; 0x030eaee8, dans 0x030eaedc
    stw   r0, 0x14(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apLvl2N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl2N@l(r11)
    stw   r3, apLvl2R3@l(r11)
    stw   r4, apLvl2R4@l(r11)
    stw   r5, apLvl2R5@l(r11)
    stw   r6, apLvl2R6@l(r11)
    stw   r7, apLvl2R7@l(r11)
    stw   r0, apLvl2Lr@l(r11)
    blr

0x030eaee8 = bla apLvlSpy2

apLvlSpy3:                    ; 0x031570c8, dans 0x031570b0
    stw   r0, 0xbc(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apLvl3N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl3N@l(r11)
    stw   r3, apLvl3R3@l(r11)
    stw   r4, apLvl3R4@l(r11)
    stw   r5, apLvl3R5@l(r11)
    stw   r6, apLvl3R6@l(r11)
    stw   r7, apLvl3R7@l(r11)
    stw   r0, apLvl3Lr@l(r11)
    blr

0x031570c8 = bla apLvlSpy3

apLvlSpy4:                    ; 0x03158b6c, dans 0x03158b58
    stw   r0, 0x2c(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apLvl4N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl4N@l(r11)
    stw   r3, apLvl4R3@l(r11)
    stw   r4, apLvl4R4@l(r11)
    stw   r5, apLvl4R5@l(r11)
    stw   r6, apLvl4R6@l(r11)
    stw   r7, apLvl4R7@l(r11)
    stw   r0, apLvl4Lr@l(r11)
    blr

0x03158b6c = bla apLvlSpy4

apLvlSpy5:                    ; 0x031577b8, dans 0x031577a8
    stw   r0, 0x14(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apLvl5N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl5N@l(r11)
    stw   r3, apLvl5R3@l(r11)
    stw   r4, apLvl5R4@l(r11)
    stw   r5, apLvl5R5@l(r11)
    stw   r6, apLvl5R6@l(r11)
    stw   r7, apLvl5R7@l(r11)
    stw   r0, apLvl5Lr@l(r11)
    blr

0x031577b8 = bla apLvlSpy5

apLvlSpy6:                    ; 0x03157888, dans 0x03157874
    stw   r0, 0x1c(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apLvl6N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl6N@l(r11)
    stw   r3, apLvl6R3@l(r11)
    stw   r4, apLvl6R4@l(r11)
    stw   r5, apLvl6R5@l(r11)
    stw   r6, apLvl6R6@l(r11)
    stw   r7, apLvl6R7@l(r11)
    stw   r0, apLvl6Lr@l(r11)
    blr

0x03157888 = bla apLvlSpy6

apLvlSpy7:                    ; 0x037b89d0, dans 0x037b89c4
    stw   r0, 0x14(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apLvl7N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl7N@l(r11)
    stw   r3, apLvl7R3@l(r11)
    stw   r4, apLvl7R4@l(r11)
    stw   r5, apLvl7R5@l(r11)
    stw   r6, apLvl7R6@l(r11)
    stw   r7, apLvl7R7@l(r11)
    stw   r0, apLvl7Lr@l(r11)
    blr

0x037b89d0 = bla apLvlSpy7

apLvlSpy8:                    ; 0x037b88e4, dans 0x037b88c4
    stw   r0, 0x4(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apLvl8N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl8N@l(r11)
    stw   r3, apLvl8R3@l(r11)
    stw   r4, apLvl8R4@l(r11)
    stw   r5, apLvl8R5@l(r11)
    stw   r6, apLvl8R6@l(r11)
    stw   r7, apLvl8R7@l(r11)
    stw   r0, apLvl8Lr@l(r11)
    blr

0x037b88e4 = bla apLvlSpy8

apLvlSpy10:                    ; 0x0315de68, dans 0x0315de5c
    stw   r0, 0x14(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apLvl10N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl10N@l(r11)
    stw   r3, apLvl10R3@l(r11)
    stw   r4, apLvl10R4@l(r11)
    stw   r5, apLvl10R5@l(r11)
    stw   r6, apLvl10R6@l(r11)
    stw   r7, apLvl10R7@l(r11)
    stw   r0, apLvl10Lr@l(r11)
    blr

0x0315de68 = bla apLvlSpy10

apLvlSpy11:                    ; 0x037a5098, dans 0x037a5080
    stw   r0, 0x2a4(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apLvl11N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl11N@l(r11)
    stw   r3, apLvl11R3@l(r11)
    stw   r4, apLvl11R4@l(r11)
    stw   r5, apLvl11R5@l(r11)
    stw   r6, apLvl11R6@l(r11)
    stw   r7, apLvl11R7@l(r11)
    stw   r0, apLvl11Lr@l(r11)
    blr

0x037a5098 = bla apLvlSpy11

apLvlSpy13:                    ; 0x0378b628, dans 0x0378b60c
    stw   r0, 0x1c(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apLvl13N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl13N@l(r11)
    stw   r3, apLvl13R3@l(r11)
    stw   r4, apLvl13R4@l(r11)
    stw   r5, apLvl13R5@l(r11)
    stw   r6, apLvl13R6@l(r11)
    stw   r7, apLvl13R7@l(r11)
    stw   r0, apLvl13Lr@l(r11)
    blr

0x0378b628 = bla apLvlSpy13

apDispSpy:                       ; 0x032bc744, prologue de 0x032bc730
    ; La diffusion, a la source. r3 et r4 sont intacts : les `mr r24, r3` et
    ; `mr r25, r4` sont avant l'ancre et ne detruisent pas leur source.
    stw   r0, 0x34(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apDispN@l(r11)
    addi  r12, r12, 1
    stw   r12, apDispN@l(r11)
    stw   r3, apDispR3@l(r11)
    stw   r4, apDispR4@l(r11)
    stw   r0, apDispLr@l(r11)
    blr

0x032bc744 = bla apDispSpy

apGrantSpy:                      ; 0x02b769d4, dans 0x02b769c4
    ; Fonction des objets ACCORDES : recompense de sanctuaire, contenu de
    ; coffre, cadeau de PNJ. Le ramassage au sol ne passe jamais par la --
    ; il appelle itemGet directement en 0x02b77014.
    stw   r0, 0x24(r1)          ; origine
    lis   r11, apTick@ha
    li    r12, 1
    stw   r12, apGrantMark@l(r11)
    stw   r3, apGrantR3@l(r11)      ; pour pouvoir la REJOUER
    stw   r4, apGrantR4@l(r11)
    stw   r0, apGrantLr@l(r11)
    ; derouler le chainage des cadres : toute la chaine d'appel
    stw   r1, apStkF@l(r11)         ; le cadre courant
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL0@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL1@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL2@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL3@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL4@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL5@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL6@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL7@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL8@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL9@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL10@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL11@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL12@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL13@l(r11)
apStkEnd:
    lis   r11, apTick@ha
    ; recopier la structure de pile pendant qu'elle est VIVANTE
    lwz   r12, 0x0(r4)
    stw   r12, apGrantW0@l(r11)
    lwz   r12, 0x4(r4)
    stw   r12, apGrantW1@l(r11)
    lwz   r12, 0x8(r4)
    stw   r12, apGrantW2@l(r11)
    lwz   r12, 0xc(r4)
    stw   r12, apGrantW3@l(r11)
    lwz   r12, 0x10(r4)
    stw   r12, apGrantW4@l(r11)
    lwz   r12, 0x14(r4)
    stw   r12, apGrantW5@l(r11)
    lwz   r12, 0x18(r4)
    stw   r12, apGrantW6@l(r11)
    lwz   r12, 0x1c(r4)
    stw   r12, apGrantW7@l(r11)
    lwz   r12, 0x20(r4)
    stw   r12, apGrantW8@l(r11)
    lwz   r12, 0x24(r4)
    stw   r12, apGrantW9@l(r11)
    lwz   r12, 0x28(r4)
    stw   r12, apGrantW10@l(r11)
    lwz   r12, 0x2c(r4)
    stw   r12, apGrantW11@l(r11)
    lwz   r12, 0x30(r4)
    stw   r12, apGrantW12@l(r11)
    lwz   r12, 0x34(r4)
    stw   r12, apGrantW13@l(r11)
    lwz   r12, 0x38(r4)
    stw   r12, apGrantW14@l(r11)
    lwz   r12, 0x3c(r4)
    stw   r12, apGrantW15@l(r11)
    lwz   r12, 0x40(r4)
    stw   r12, apGrantW16@l(r11)
    lwz   r12, 0x44(r4)
    stw   r12, apGrantW17@l(r11)
    lwz   r12, 0x48(r4)
    stw   r12, apGrantW18@l(r11)
    lwz   r12, 0x4c(r4)
    stw   r12, apGrantW19@l(r11)
    lwz   r12, 0x50(r4)
    stw   r12, apGrantW20@l(r11)
    lwz   r12, 0x54(r4)
    stw   r12, apGrantW21@l(r11)
    lwz   r12, 0x58(r4)
    stw   r12, apGrantW22@l(r11)
    lwz   r12, 0x5c(r4)
    stw   r12, apGrantW23@l(r11)
    lwz   r12, 0x60(r4)
    stw   r12, apGrantW24@l(r11)
    lwz   r12, 0x64(r4)
    stw   r12, apGrantW25@l(r11)
    lwz   r12, 0x68(r4)
    stw   r12, apGrantW26@l(r11)
    lwz   r12, 0x6c(r4)
    stw   r12, apGrantW27@l(r11)
    lwz   r12, 0x70(r4)
    stw   r12, apGrantW28@l(r11)
    lwz   r12, 0x74(r4)
    stw   r12, apGrantW29@l(r11)
    lwz   r12, 0x78(r4)
    stw   r12, apGrantW30@l(r11)
    lwz   r12, 0x7c(r4)
    stw   r12, apGrantW31@l(r11)
    lwz   r12, apGrantN@l(r11)
    addi  r12, r12, 1
    stw   r12, apGrantN@l(r11)

    ; --- armement automatique de la substitution de texte ----------------
    ; On est sur le chemin des objets ACCORDES, et avant itemGet : c'est le
    ; seul instant ou l'on sait que la fenetre du coffre va se construire.
    lwz   r12, apSubAuto@l(r11)
    cmpwi r12, 0
    beq   apGrantEnd
    addi  r12, r12, -1
    stw   r12, apSubAuto@l(r11)
    lwz   r12, apSubAutoN@l(r11)
    stw   r12, apSubReq@l(r11)
    stw   r12, apSubDescReq@l(r11)
apGrantEnd:
    blr

0x02b769d4 = bla apGrantSpy

0x031FA97C = bla apProbe
0x02EB5400 = bla apItemGetSpy

; --- sondes PickUpWin -------------------------------------------------
; Chaque sonde rejoue l'instruction d'origine, allume son bit dans
; apHookMask et incremente son compteur. Ancrage place APRES le mflr de
; chaque fonction : avant, le bla de Cemu detruirait son adresse de retour.
; Seuls r11 et r12 sont touches -- volatils, donc morts dans un prologue.

apProbe0:                      ; fonction 0x02ffa888
    mr    r26, r3          ; origine
    lis   r11, apTick@ha
    stw   r3, apPickUpThis@l(r11)   ; instance de l'ecran, pour pouvoir rappeler
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0001
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook0@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook0@l(r11)
    blr

apProbe1:                      ; fonction 0x02ffb11c
    mr    r24, r3          ; origine
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0002
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook1@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook1@l(r11)
    blr

apProbe2:                      ; fonction 0x02ffb654
    stfd  f29, 0xa8(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0004
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook2@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook2@l(r11)
    blr

apProbe3:                      ; fonction 0x02ffc8f8
    stw   r0, 0x44(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0008
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook3@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook3@l(r11)
    blr

apProbe4:                      ; fonction 0x02ffccf0
    mr    r31, r3          ; origine
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0010
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook4@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook4@l(r11)
    blr

apProbe5:                      ; fonction 0x02ffcdc4
    mr    r31, r3          ; origine
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0020
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook5@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook5@l(r11)
    blr

apProbe6:                      ; fonction 0x02ffceac
    mr    r31, r3          ; origine
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0040
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook6@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook6@l(r11)
    blr

apProbe7:                      ; fonction 0x02ffcf80
    mr    r31, r3          ; origine
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0080
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook7@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook7@l(r11)
    blr

apProbe8:                      ; fonction 0x02ffd06c
    mr    r31, r3          ; origine
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0100
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook8@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook8@l(r11)
    blr
0x02ffa894 = bla apProbe0
0x02ffb128 = bla apProbe1
0x02ffb660 = bla apProbe2
0x02ffc90c = bla apProbe3
0x02ffccfc = bla apProbe4
0x02ffcdd0 = bla apProbe5
0x02ffceb8 = bla apProbe6
0x02ffcf8c = bla apProbe7
0x02ffd078 = bla apProbe8
0x02FFAB18 = bla apProbeScreen
0x02ecbcbc = bla apMSProbe0
0x02ed1a7c = bla apMSProbe1
0x02f21990 = bla apMSProbe2
0x02f8b2d4 = bla apMSProbe3
0x02fc0f80 = bla apMSProbe4
0x02fc2e00 = bla apMSProbe5
0x02ed1e98 = bla apMSTracePass
0x02ed1e5c = bla apMSTraceBail
0x02ed1e70 = bla apMSTraceMid
0x02ed1f98 = bla apPushSpy

; --- sondes de la fenetre d'obtention d'objet ---------------------------
; Chaque sonde rejoue le `stw r0, N(r1)` qui vient de sauver LR : a ce point
; r0 est mort (sa valeur est deja sur la pile) et r11/r12 sont volatils, donc
; morts dans un prologue. checkhooks.py le verifie sur les 40 hooks.

apGetProbe0:                    ; 0x02fcf2a4, fonction 0x02fcf29c
    stw   r0, 0x94(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet0@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet0@l(r11)
    stw   r0, apGetFrom0@l(r11)
    stw   r3, apGetThis0@l(r11)
    stw   r4, apGetR4_0@l(r11)
    stw   r5, apGetR5_0@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd0@l(r11)
    blr

apGetProbe1:                    ; 0x02fcf64c, fonction 0x02fcf63c
    stw   r0, 0x64(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet1@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet1@l(r11)
    stw   r0, apGetFrom1@l(r11)
    stw   r3, apGetThis1@l(r11)
    stw   r4, apGetR4_1@l(r11)
    stw   r5, apGetR5_1@l(r11)
    ; Cette sonde n'est traversee que quand MessageGet_00 s'ouvre : la capture
    ; en attente du pilote est donc celle de CET ecran. On la fige.
    lwz   r12, apGetDrvThis@l(r11)
    stw   r12, apGetWinCThis@l(r11)
    lwz   r12, apGetDrvA4@l(r11)
    stw   r12, apGetWinCA4@l(r11)
    lwz   r12, apGetDrvA5@l(r11)
    stw   r12, apGetWinCA5@l(r11)
    lwz   r12, apGetDrvA6@l(r11)
    stw   r12, apGetWinCA6@l(r11)
    lwz   r12, apGetDrvA7@l(r11)
    stw   r12, apGetWinCA7@l(r11)
    lwz   r12, apGetDrvA8@l(r11)
    stw   r12, apGetWinCA8@l(r11)
    lwz   r12, apGetDrvA9@l(r11)
    stw   r12, apGetWinCA9@l(r11)
    lwz   r12, apGetWinOk@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWinOk@l(r11)
    ; et les six registres du site d'ouverture, meme raison
    lwz   r12, apOpn24@l(r11)
    stw   r12, apOpnC24@l(r11)
    lwz   r12, apOpn25@l(r11)
    stw   r12, apOpnC25@l(r11)
    lwz   r12, apOpn26@l(r11)
    stw   r12, apOpnC26@l(r11)
    lwz   r12, apOpn27@l(r11)
    stw   r12, apOpnC27@l(r11)
    lwz   r12, apOpn28@l(r11)
    stw   r12, apOpnC28@l(r11)
    lwz   r12, apOpn31@l(r11)
    stw   r12, apOpnC31@l(r11)
    lwz   r12, apOpnOk@l(r11)
    addi  r12, r12, 1
    stw   r12, apOpnOk@l(r11)

    ; et les six ARGUMENTS du prologue, meme raison : le prologue tourne a
    ; chaque ouverture d'ecran, seule cette sonde-ci sait que c'est la notre
    lwz   r12, apOpnProLr@l(r11)
    stw   r12, apOpnPrcLr@l(r11)
    lwz   r12, apOpnProR1@l(r11)
    stw   r12, apOpnPrcR1@l(r11)
    lwz   r12, apOpnProA1@l(r11)
    stw   r12, apOpnPrcA1@l(r11)
    lwz   r12, apOpnProA2@l(r11)
    stw   r12, apOpnPrcA2@l(r11)
    lwz   r12, apOpnProA3@l(r11)
    stw   r12, apOpnPrcA3@l(r11)
    lwz   r12, apOpnProA4@l(r11)
    stw   r12, apOpnPrcA4@l(r11)
    lwz   r12, apOpnProA5@l(r11)
    stw   r12, apOpnPrcA5@l(r11)
    lwz   r12, apOpnProA6@l(r11)
    stw   r12, apOpnPrcA6@l(r11)
    lwz   r12, apOpnPrcOk@l(r11)
    addi  r12, r12, 1
    stw   r12, apOpnPrcOk@l(r11)

    ; et les cinq arguments de l'etage du dessus, meme raison
    lwz   r12, apUpA1@l(r11)
    stw   r12, apUpcA1@l(r11)
    lwz   r12, apUpA2@l(r11)
    stw   r12, apUpcA2@l(r11)
    lwz   r12, apUpA3@l(r11)
    stw   r12, apUpcA3@l(r11)
    lwz   r12, apUpA4@l(r11)
    stw   r12, apUpcA4@l(r11)
    lwz   r12, apUpA5@l(r11)
    stw   r12, apUpcA5@l(r11)
    lwz   r12, apUpcOk@l(r11)
    addi  r12, r12, 1
    stw   r12, apUpcOk@l(r11)

    ; recopier l'objet de contexte pendant qu'il est VIVANT
    stw   r3, apOpnCtxR3@l(r11)
    lwz   r3, apOpn31@l(r11)
    lwz   r12, 0x0(r3)
    stw   r12, apOpnCtx0@l(r11)
    lwz   r12, 0x4(r3)
    stw   r12, apOpnCtx1@l(r11)
    lwz   r12, 0x8(r3)
    stw   r12, apOpnCtx2@l(r11)
    lwz   r12, 0xc(r3)
    stw   r12, apOpnCtx3@l(r11)
    lwz   r12, 0x10(r3)
    stw   r12, apOpnCtx4@l(r11)
    lwz   r12, 0x14(r3)
    stw   r12, apOpnCtx5@l(r11)
    lwz   r12, 0x18(r3)
    stw   r12, apOpnCtx6@l(r11)
    lwz   r12, 0x1c(r3)
    stw   r12, apOpnCtx7@l(r11)
    lwz   r12, 0x20(r3)
    stw   r12, apOpnCtx8@l(r11)
    lwz   r12, 0x24(r3)
    stw   r12, apOpnCtx9@l(r11)
    lwz   r12, 0x28(r3)
    stw   r12, apOpnCtx10@l(r11)
    lwz   r12, 0x2c(r3)
    stw   r12, apOpnCtx11@l(r11)
    lwz   r12, 0x30(r3)
    stw   r12, apOpnCtx12@l(r11)
    lwz   r12, 0x34(r3)
    stw   r12, apOpnCtx13@l(r11)
    lwz   r12, 0x38(r3)
    stw   r12, apOpnCtx14@l(r11)
    lwz   r12, 0x3c(r3)
    stw   r12, apOpnCtx15@l(r11)
    lwz   r12, 0x40(r3)
    stw   r12, apOpnCtx16@l(r11)
    lwz   r12, 0x44(r3)
    stw   r12, apOpnCtx17@l(r11)
    lwz   r12, 0x48(r3)
    stw   r12, apOpnCtx18@l(r11)
    lwz   r12, 0x4c(r3)
    stw   r12, apOpnCtx19@l(r11)
    lwz   r12, 0x50(r3)
    stw   r12, apOpnCtx20@l(r11)
    lwz   r12, 0x54(r3)
    stw   r12, apOpnCtx21@l(r11)
    lwz   r12, 0x58(r3)
    stw   r12, apOpnCtx22@l(r11)
    lwz   r12, 0x5c(r3)
    stw   r12, apOpnCtx23@l(r11)
    lwz   r12, 0x60(r3)
    stw   r12, apOpnCtx24@l(r11)
    lwz   r12, 0x64(r3)
    stw   r12, apOpnCtx25@l(r11)
    lwz   r12, 0x68(r3)
    stw   r12, apOpnCtx26@l(r11)
    lwz   r12, 0x6c(r3)
    stw   r12, apOpnCtx27@l(r11)
    lwz   r12, 0x70(r3)
    stw   r12, apOpnCtx28@l(r11)
    lwz   r12, 0x74(r3)
    stw   r12, apOpnCtx29@l(r11)
    lwz   r12, 0x78(r3)
    stw   r12, apOpnCtx30@l(r11)
    lwz   r12, 0x7c(r3)
    stw   r12, apOpnCtx31@l(r11)
    lwz   r3, apOpnCtxR3@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd1@l(r11)
    blr

apGetProbe2:                    ; 0x02fd0330, fonction 0x02fd0314
    stw   r0, 0x44(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet2@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet2@l(r11)
    stw   r0, apGetFrom2@l(r11)
    stw   r3, apGetThis2@l(r11)
    stw   r4, apGetR4_2@l(r11)
    stw   r5, apGetR5_2@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd2@l(r11)
    blr

apGetProbe3:                    ; 0x02fd0cfc, fonction 0x02fd0ce4
    stw   r0, 0x19c(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet3@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet3@l(r11)
    stw   r0, apGetFrom3@l(r11)
    stw   r3, apGetThis3@l(r11)
    stw   r4, apGetR4_3@l(r11)
    stw   r5, apGetR5_3@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd3@l(r11)
    blr

apGetProbe4:                    ; 0x02fd14f8, fonction 0x02fd14e8
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet4@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet4@l(r11)
    stw   r0, apGetFrom4@l(r11)
    stw   r3, apGetThis4@l(r11)
    stw   r4, apGetR4_4@l(r11)
    stw   r5, apGetR5_4@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd4@l(r11)
    blr

apGetProbe5:                    ; 0x02fd1544, fonction 0x02fd1534
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet5@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet5@l(r11)
    stw   r0, apGetFrom5@l(r11)
    stw   r3, apGetThis5@l(r11)
    stw   r4, apGetR4_5@l(r11)
    stw   r5, apGetR5_5@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd5@l(r11)
    blr

apGetProbe6:                    ; 0x02fd166c, fonction 0x02fd165c
    stw   r0, 0x24(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet6@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet6@l(r11)
    stw   r0, apGetFrom6@l(r11)
    stw   r3, apGetThis6@l(r11)
    stw   r4, apGetR4_6@l(r11)
    stw   r5, apGetR5_6@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd6@l(r11)
    blr

apGetProbe7:                    ; 0x02fd1ee4, fonction 0x02fd1ed8
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet7@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet7@l(r11)
    stw   r0, apGetFrom7@l(r11)
    stw   r3, apGetThis7@l(r11)
    stw   r4, apGetR4_7@l(r11)
    stw   r5, apGetR5_7@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd7@l(r11)
    blr

apGetProbe8:                    ; 0x02fd20e0, fonction 0x02fd20cc
    stw   r0, 0x24(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet8@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet8@l(r11)
    stw   r0, apGetFrom8@l(r11)
    stw   r3, apGetThis8@l(r11)
    stw   r4, apGetR4_8@l(r11)
    stw   r5, apGetR5_8@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd8@l(r11)
    blr

apGetProbe9:                    ; 0x02fd21e0, fonction 0x02fd21cc
    stw   r0, 0x24(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet9@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet9@l(r11)
    stw   r0, apGetFrom9@l(r11)
    stw   r3, apGetThis9@l(r11)
    stw   r4, apGetR4_9@l(r11)
    stw   r5, apGetR5_9@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd9@l(r11)
    blr

apGetProbe10:                    ; 0x02fd22b4, fonction 0x02fd22a0
    stw   r0, 0x24(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet10@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet10@l(r11)
    stw   r0, apGetFrom10@l(r11)
    stw   r3, apGetThis10@l(r11)
    stw   r4, apGetR4_10@l(r11)
    stw   r5, apGetR5_10@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd10@l(r11)
    blr

apGetProbe11:                    ; 0x02fd2408, fonction 0x02fd23f4
    stw   r0, 0x1c(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet11@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet11@l(r11)
    stw   r0, apGetFrom11@l(r11)
    stw   r3, apGetThis11@l(r11)
    stw   r4, apGetR4_11@l(r11)
    stw   r5, apGetR5_11@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd11@l(r11)
    blr

apGetProbe12:                    ; 0x02fd2524, fonction 0x02fd2510
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet12@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet12@l(r11)
    stw   r0, apGetFrom12@l(r11)
    stw   r3, apGetThis12@l(r11)
    stw   r4, apGetR4_12@l(r11)
    stw   r5, apGetR5_12@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd12@l(r11)
    blr

apGetProbe13:                    ; 0x02fd2570, fonction 0x02fd255c
    stw   r0, 0x84(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet13@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet13@l(r11)
    stw   r0, apGetFrom13@l(r11)
    stw   r3, apGetThis13@l(r11)
    stw   r4, apGetR4_13@l(r11)
    stw   r5, apGetR5_13@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd13@l(r11)
    blr

apGetProbe14:                    ; 0x02fd2b34, fonction 0x02fd2b18
    stw   r0, 0x124(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet14@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet14@l(r11)
    stw   r0, apGetFrom14@l(r11)
    stw   r3, apGetThis14@l(r11)
    stw   r4, apGetR4_14@l(r11)
    stw   r5, apGetR5_14@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd14@l(r11)
    blr

apGetProbe15:                    ; 0x02fd2d74, fonction 0x02fd2d64
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet15@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet15@l(r11)
    stw   r0, apGetFrom15@l(r11)
    stw   r3, apGetThis15@l(r11)
    stw   r4, apGetR4_15@l(r11)
    stw   r5, apGetR5_15@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd15@l(r11)
    blr

apGetProbe16:                    ; 0x02fd2ffc, fonction 0x02fd2ff0
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet16@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet16@l(r11)
    stw   r0, apGetFrom16@l(r11)
    stw   r3, apGetThis16@l(r11)
    stw   r4, apGetR4_16@l(r11)
    stw   r5, apGetR5_16@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd16@l(r11)
    blr

apGetProbe17:                    ; 0x02fd3048, fonction 0x02fd3034
    stw   r0, 0x13c(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet17@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet17@l(r11)
    stw   r0, apGetFrom17@l(r11)
    stw   r3, apGetThis17@l(r11)
    stw   r4, apGetR4_17@l(r11)
    stw   r5, apGetR5_17@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd17@l(r11)
    blr

apGetProbe18:                    ; 0x02fd33f0, fonction 0x02fd33e0
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGet18@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet18@l(r11)
    stw   r0, apGetFrom18@l(r11)
    stw   r3, apGetThis18@l(r11)
    stw   r4, apGetR4_18@l(r11)
    stw   r5, apGetR5_18@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd18@l(r11)
    blr

0x02fcf2a4 = bla apGetProbe0
0x02fcf64c = bla apGetProbe1
0x02fd0330 = bla apGetProbe2
0x02fd0cfc = bla apGetProbe3
0x02fd14f8 = bla apGetProbe4
0x02fd1544 = bla apGetProbe5
0x02fd166c = bla apGetProbe6
0x02fd1ee4 = bla apGetProbe7
0x02fd20e0 = bla apGetProbe8
0x02fd21e0 = bla apGetProbe9
0x02fd22b4 = bla apGetProbe10
0x02fd2408 = bla apGetProbe11
0x02fd2524 = bla apGetProbe12
0x02fd2570 = bla apGetProbe13
0x02fd2b34 = bla apGetProbe14
0x02fd2d74 = bla apGetProbe15
0x02fd2ffc = bla apGetProbe16
0x02fd3048 = bla apGetProbe17
0x02fd33f0 = bla apGetProbe18

; --- sondes de la classe gestionnaire de la fenetre d'obtention ---------

apGetWinProbe0:                 ; 0x03606ae8, fonction 0x03606ad0
    stw   r0, 0x3c(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetWin0@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin0@l(r11)
    stw   r0, apGetWinFrom0@l(r11)
    stw   r3, apGetWinThis0@l(r11)
    stw   r4, apGetWinR4_0@l(r11)
    stw   r5, apGetWinR5_0@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd0@l(r11)
    blr

apGetWinProbe1:                 ; 0x03606c74, fonction 0x03606c5c
    stw   r0, 0x3c(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetWin1@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin1@l(r11)
    stw   r0, apGetWinFrom1@l(r11)
    stw   r3, apGetWinThis1@l(r11)
    stw   r4, apGetWinR4_1@l(r11)
    stw   r5, apGetWinR5_1@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd1@l(r11)
    blr

apGetWinProbe2:                 ; 0x03606e2c, fonction 0x03606e18
    stw   r0, 0x34(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetWin2@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin2@l(r11)
    stw   r0, apGetWinFrom2@l(r11)
    stw   r3, apGetWinThis2@l(r11)
    stw   r4, apGetWinR4_2@l(r11)
    stw   r5, apGetWinR5_2@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd2@l(r11)
    blr

apGetWinProbe3:                 ; 0x03606ee8, fonction 0x03606ed4
    stw   r0, 0x1c(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetWin3@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin3@l(r11)
    stw   r0, apGetWinFrom3@l(r11)
    stw   r3, apGetWinThis3@l(r11)
    stw   r4, apGetWinR4_3@l(r11)
    stw   r5, apGetWinR5_3@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd3@l(r11)
    blr

apGetWinProbe4:                 ; 0x03606f58, fonction 0x03606f48
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetWin4@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin4@l(r11)
    stw   r0, apGetWinFrom4@l(r11)
    stw   r3, apGetWinThis4@l(r11)
    stw   r4, apGetWinR4_4@l(r11)
    stw   r5, apGetWinR5_4@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd4@l(r11)
    blr

apGetWinProbe5:                 ; 0x036070a8, fonction 0x03607080
    stw   r0, 0x54(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetWin5@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin5@l(r11)
    stw   r0, apGetWinFrom5@l(r11)
    stw   r3, apGetWinThis5@l(r11)
    stw   r4, apGetWinR4_5@l(r11)
    stw   r5, apGetWinR5_5@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd5@l(r11)
    blr

apGetWinProbe6:                 ; 0x03607220, fonction 0x03607210
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    stw   r1, apR1Ui@l(r11)         ; pile du gestionnaire d'interface
    lwz   r12, apGetWin6@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin6@l(r11)
    stw   r0, apGetWinFrom6@l(r11)
    stw   r3, apGetWinThis6@l(r11)
    stw   r4, apGetWinR4_6@l(r11)
    stw   r5, apGetWinR5_6@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd6@l(r11)

    ; --- maintenir la fenetre d'obtention ouverte ------------------------
    ; Chaque maillon verifie avant d'etre suivi. Si la case est vide on ne
    ; touche a RIEN -- surtout pas a l'octet d'activite : le poser sur un
    ; index sans ecran ferait suivre au pilote un pointeur mort a l'image
    ; suivante. Une version Python de ce maintien a fait exactement ca.
    lwz   r12, apHoldN@l(r11)
    cmpwi r12, 0
    beq   apHoldEnd
    addi  r12, r12, -1
    stw   r12, apHoldN@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    lis   r12, 0x1047
    ori   r12, r12, 0xe650
    lwz   r3, 0x0(r12)
    cmpwi r3, 0
    beq   apHoldPop
    lwz   r4, 0x18(r3)
    cmpwi r4, 0
    beq   apHoldPop
    lwz   r4, 0x2c(r4)              ; case 0x0b
    cmpwi r4, 0
    beq   apHoldPop
    ; MESURE : la premiere version ecrivait 0x200 dans +0x94 ET 0 dans
    ; l'octet d'activite A CHAQUE IMAGE, sans condition. L'ecran a bien tenu
    ; -- mais le jeu a gele puis plante : on ecrasait soixante fois par
    ; seconde les autres bits que la machine a etats pose pendant
    ; l'animation. On ne corrige donc plus QUE la valeur exacte relevee comme
    ; demande de fermeture, et rien d'autre.
    lwz   r12, 0x94(r4)
    cmpwi r12, 0x300
    bne   apHoldPop
    li    r12, 0x200
    stw   r12, 0x94(r4)
apHoldPop:
    lis   r11, apTick@ha
    lwz   r3, apS3@l(r11)
    lwz   r4, apS4@l(r11)
apHoldEnd:

    ; --- d'ou vient un TAS VIVANT ? sonde du getter de tas courant -------
    ; Le createur de tas ET l'allocateur butent tous deux sur 0x030aa1ac.
    ; On l'interroge donc directement, depuis CE fil -- celui de l'IHM, le
    ; seul de la bonne famille de pile. Tout deref est garde : le getter
    ; suit *(0x1046C920) puis +0x60 sans rien tester, et rend *(arg + 0x4)
    ; en repli, donc on refuse si l'un des deux est nul.
    lwz   r12, apHeapReq@l(r11)
    cmpwi r12, 0
    beq   apHeapEnd

    li    r12, 0
    stw   r12, apHeapReq@l(r11)
    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    lwz   r12, apHeapN@l(r11)
    addi  r12, r12, 1
    stw   r12, apHeapN@l(r11)

    ; les deux statiques dont le getter se sert
    lis   r12, 0x1046
    ori   r12, r12, 0xc8b0
    lwz   r3, 0x0(r12)              ; *(0x1046C8B0) : l'argument du createur
    stw   r3, apHeapRoot@l(r11)
    lis   r12, 0x1046
    ori   r12, r12, 0xc920
    lwz   r12, 0x0(r12)             ; *(0x1046C920) : d'ou sort le fil
    stw   r12, apHeapMgr@l(r11)

    ; le repli statique du getter, *(root + 0x4)
    cmpwi r3, 0
    beq   apHeapDone
    lwz   r12, 0x4(r3)
    stw   r12, apHeapFb@l(r11)

    ; l'appel lui-meme, seulement si les deux deref du getter sont surs
    lis   r12, 0x1046
    ori   r12, r12, 0xc920
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apHeapDone
    lis   r12, 0x030a
    ori   r12, r12, 0xa1ac
    mtctr r12
    bctrl
    lis   r11, apTick@ha
    stw   r3, apHeapCur@l(r11)

apHeapDone:
    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)
apHeapEnd:

    ; --- rejouer l'ouverture de la fenetre, ICI et pas ailleurs ----------
    ; MESURE : le vrai site d'ouverture tourne sur la pile 0x12b3c510, quand
    ; le hook per-frame tourne sur 0x0e201270 -- deux threads. Quatre
    ; plantages ont suivi d'un rejeu depuis le mauvais. Cette fonction-ci
    ; s'execute a chaque image sur la pile 0x12afc088, la meme famille que le
    ; site reel. C'est de la qu'il faut appeler.
    lwz   r12, apOpnReq@l(r11)
    cmpwi r12, 0
    beq   apGetWinProbe6End

    lwz   r12, apOpnOk@l(r11)
    cmpwi r12, 0
    beq   apGetWinProbe6End         ; MessageGet_00 jamais vu : ne rien tenter

    li    r12, 0
    stw   r12, apOpnReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; 0) restaurer l'objet de contexte -- COUPE PAR DEFAUT.
    ; apOpnC31 est un tas deja libere. Y recopier 32 mots n'a jamais rien
    ; debloque, et ecrire dans l'en-tete d'un tas mort peut abimer
    ; l'allocateur. Python rallume avec --ctx pour refaire les mesures
    ; anterieures.
    lwz   r12, apOpnCtxOn@l(r11)
    cmpwi r12, 0
    beq   apOpnNoCtx
    lwz   r3, apOpnC31@l(r11)
    lwz   r12, apOpnCtx0@l(r11)
    stw   r12, 0x0(r3)
    lwz   r12, apOpnCtx1@l(r11)
    stw   r12, 0x4(r3)
    lwz   r12, apOpnCtx2@l(r11)
    stw   r12, 0x8(r3)
    lwz   r12, apOpnCtx3@l(r11)
    stw   r12, 0xc(r3)
    lwz   r12, apOpnCtx4@l(r11)
    stw   r12, 0x10(r3)
    lwz   r12, apOpnCtx5@l(r11)
    stw   r12, 0x14(r3)
    lwz   r12, apOpnCtx6@l(r11)
    stw   r12, 0x18(r3)
    lwz   r12, apOpnCtx7@l(r11)
    stw   r12, 0x1c(r3)
    lwz   r12, apOpnCtx8@l(r11)
    stw   r12, 0x20(r3)
    lwz   r12, apOpnCtx9@l(r11)
    stw   r12, 0x24(r3)
    lwz   r12, apOpnCtx10@l(r11)
    stw   r12, 0x28(r3)
    lwz   r12, apOpnCtx11@l(r11)
    stw   r12, 0x2c(r3)
    lwz   r12, apOpnCtx12@l(r11)
    stw   r12, 0x30(r3)
    lwz   r12, apOpnCtx13@l(r11)
    stw   r12, 0x34(r3)
    lwz   r12, apOpnCtx14@l(r11)
    stw   r12, 0x38(r3)
    lwz   r12, apOpnCtx15@l(r11)
    stw   r12, 0x3c(r3)
    lwz   r12, apOpnCtx16@l(r11)
    stw   r12, 0x40(r3)
    lwz   r12, apOpnCtx17@l(r11)
    stw   r12, 0x44(r3)
    lwz   r12, apOpnCtx18@l(r11)
    stw   r12, 0x48(r3)
    lwz   r12, apOpnCtx19@l(r11)
    stw   r12, 0x4c(r3)
    lwz   r12, apOpnCtx20@l(r11)
    stw   r12, 0x50(r3)
    lwz   r12, apOpnCtx21@l(r11)
    stw   r12, 0x54(r3)
    lwz   r12, apOpnCtx22@l(r11)
    stw   r12, 0x58(r3)
    lwz   r12, apOpnCtx23@l(r11)
    stw   r12, 0x5c(r3)
    lwz   r12, apOpnCtx24@l(r11)
    stw   r12, 0x60(r3)
    lwz   r12, apOpnCtx25@l(r11)
    stw   r12, 0x64(r3)
    lwz   r12, apOpnCtx26@l(r11)
    stw   r12, 0x68(r3)
    lwz   r12, apOpnCtx27@l(r11)
    stw   r12, 0x6c(r3)
    lwz   r12, apOpnCtx28@l(r11)
    stw   r12, 0x70(r3)
    lwz   r12, apOpnCtx29@l(r11)
    stw   r12, 0x74(r3)
    lwz   r12, apOpnCtx30@l(r11)
    stw   r12, 0x78(r3)
    lwz   r12, apOpnCtx31@l(r11)
    stw   r12, 0x7c(r3)
apOpnNoCtx:

    ; 1) obtenir l'ecran
    li    r12, 1
    stw   r12, apOpnPhase@l(r11)

    lwz   r12, apOpnMode@l(r11)
    cmpwi r12, 8
    beq   apOpnCall
    cmpwi r12, 7
    beq   apOpnDisp
    cmpwi r12, 6
    beq   apOpnGrant
    cmpwi r12, 5
    beq   apOpnVCall
    cmpwi r12, 4
    beq   apOpnShow
    cmpwi r12, 3
    beq   apOpnUp
    cmpwi r12, 2
    beq   apOpnWhole
    cmpwi r12, 1
    bne   apOpnFabrique

    ; --- le trampoline, comme la boite de dialogue -----------------------
    lwz   r3, apOpnC28@l(r11)   ; l'index, 0x0b
    li    r4, 0
    lis   r12, 0x0339
    ori   r12, r12, 0x24c4
    mtctr r12
    bctrl
    b     apOpnGot

apOpnCall:
    ; --- L'INVOCATEUR GENERIQUE ------------------------------------------
    ; Huit arguments, une adresse, aucune hypothese. Python verifie ce qu'il
    ; passe ; ici on ne garde que le saut lui-meme.
    lwz   r12, apCallAddr@l(r11)
    cmpwi r12, 0
    beq   apOpnShowNo
    mtctr r12
    lwz   r3, apCallA1@l(r11)
    lwz   r4, apCallA2@l(r11)
    lwz   r5, apCallA3@l(r11)
    lwz   r6, apCallA4@l(r11)
    lwz   r7, apCallA5@l(r11)
    lwz   r8, apCallA6@l(r11)
    lwz   r9, apCallA7@l(r11)
    lwz   r10, apCallA8@l(r11)
    bctrl
    lis   r11, apTick@ha
    stw   r3, apCallRet@l(r11)
    lwz   r12, apCallN@l(r11)
    addi  r12, r12, 1
    stw   r12, apCallN@l(r11)
    li    r12, 14
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnDisp:
    ; --- LA DIFFUSION : 0x032bc730(*(0x1047D6C0), nom) -------------------
    ; Le statique est relu ici et verifie ; le nom vient de apGrantName, que
    ; Python pose (capture par defaut, ou notre propre chaine).
    lwz   r4, apGrantName@l(r11)
    cmpwi r4, 0
    beq   apOpnShowNo
    lwz   r3, apDispArg@l(r11)      ; MESURE, pas calcul
    cmpwi r3, 0
    beq   apOpnShowNo
    lis   r12, 0x032b
    ori   r12, r12, 0xc730
    mtctr r12
    bctrl
    lis   r11, apTick@ha
    stw   r3, apOpnR3@l(r11)
    li    r12, 13
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnGrant:
    ; --- LE SOMMET : 0x02b769c4(r3, r4), l'objet accorde -----------------
    ; Aucun deref ici : on repasse les deux arguments captures, la fonction
    ; fait tout le reste. On refuse seulement si la capture est vide.
    lwz   r3, apGrantR3@l(r11)
    cmpwi r3, 0
    beq   apOpnShowNo
    ; notre copie, pas le pointeur de pile mort
    lwz   r4, apGrantBufPtr@l(r11)
    cmpwi r4, 0
    beq   apOpnShowNo
    lis   r12, 0x02b7
    ori   r12, r12, 0x69c4
    mtctr r12
    bctrl
    lis   r11, apTick@ha
    stw   r3, apOpnR3@l(r11)
    li    r12, 12
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnVCall:
    ; --- LA FONCTION ENGLOBANTE de la mise en scene ----------------------
    ; ecran->vtable[0x1a4](ecran, mode) = 0x03a40d20. C'est la manoeuvre qui
    ; a debloque deux fois : appeler l'englobante plutot que reproduire son
    ; interieur. Chaque maillon verifie ; phase 11 si on est revenu.
    lwz   r9, apOpnVArg@l(r11)
    lis   r12, 0x1047
    ori   r12, r12, 0xe650
    lwz   r8, 0x0(r12)
    cmpwi r8, 0
    beq   apOpnShowNo
    lwz   r8, 0x18(r8)
    cmpwi r8, 0
    beq   apOpnShowNo
    lwz   r8, 0x2c(r8)              ; case 0x0b
    cmpwi r8, 0
    beq   apOpnShowNo
    lwz   r12, 0xc(r8)
    cmpwi r12, 0
    beq   apOpnShowNo
    lwz   r0, 0x1a4(r12)
    cmpwi r0, 0
    beq   apOpnShowNo
    mtctr r0
    mr    r3, r8
    mr    r4, r9
    bctrl
    lis   r11, apTick@ha
    li    r12, 11
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnShow:
    ; --- AFFICHER un ecran deja construit --------------------------------
    ; Rejoue les quatre gestes de 0x03a40ebc sur l'ecran range en case 0x0b.
    ; Chaque maillon est verifie avant d'etre suivi : le gestionnaire, la
    ; table, la case, la vtable, puis chacune des deux fentes. Un maillon nul
    ; laisse apOpnPhase a 10 au lieu de fermer Cemu.
    lwz   r9, apOpnAnim@l(r11)      ; garder le drapeau avant de perdre r11
    lis   r12, 0x1047
    ori   r12, r12, 0xe650
    lwz   r8, 0x0(r12)              ; le gestionnaire
    cmpwi r8, 0
    beq   apOpnShowNo
    lwz   r8, 0x18(r8)              ; sa table d'ecrans
    cmpwi r8, 0
    beq   apOpnShowNo
    lwz   r8, 0x2c(r8)              ; case 0x0b -- 0x0b * 4
    cmpwi r8, 0
    beq   apOpnShowNo
    lwz   r12, 0xc(r8)              ; la vtable de l'ecran
    cmpwi r12, 0
    beq   apOpnShowNo

    ; 1) l'animation : vtable[0x214](ecran, "open")
    cmpwi r9, 0
    beq   apOpnShowNoAnim
    lwz   r0, 0x214(r12)
    cmpwi r0, 0
    beq   apOpnShowNoAnim
    mtctr r0
    mr    r3, r8
    lis   r4, 0x1035
    ori   r4, r4, 0xdb30            ; la chaine "open"
    bctrl
apOpnShowNoAnim:

    ; 2) les trois octets
    li    r10, 0
    stb   r10, 0x9e(r8)
    stb   r10, 0x97(r8)
    li    r10, 1
    stb   r10, 0x96(r8)

    ; 3) l'entree : vtable[0x114](ecran) = 0x036072e0
    lwz   r12, 0xc(r8)
    cmpwi r12, 0
    beq   apOpnShowNo
    lwz   r0, 0x114(r12)
    cmpwi r0, 0
    beq   apOpnShowNo
    mtctr r0
    mr    r3, r8
    bctrl

    lis   r11, apTick@ha
    li    r12, 9
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnShowNo:
    lis   r11, apTick@ha
    li    r12, 10
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnUp:
    ; --- L'ETAGE DU DESSUS, 0x030806f0(a1..a5) ---------------------------
    ; Il appelle 0x03a42b94 lui-meme, puis enchaine la mise en scene que
    ; notre rejeu sautait. Les cinq arguments viennent de la capture figee
    ; sur MessageGet_00. Aucun deref ici.
    lwz   r3, apUpcA1@l(r11)
    lwz   r4, apUpcA2@l(r11)
    lwz   r5, apUpcA3@l(r11)
    lwz   r6, apUpcA4@l(r11)
    lwz   r7, apUpcA5@l(r11)
    lis   r12, 0x0308
    ori   r12, r12, 0x06f0
    mtctr r12
    bctrl
    lis   r11, apTick@ha
    stw   r3, apOpnR3@l(r11)
    li    r12, 8
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnWhole:
    ; --- la FONCTION ENGLOBANTE, celle qui sait se creer un tas ----------
    ; 0x03a42b94(r3..r8). r31 y est l'argument 6 et r30 l'argument 2 ; quand
    ; les deux sont nuls elle branche en 0x03a42c90 et cree son tas. Rejouer
    ; depuis 0x03a42ccc sautait justement par-dessus cette creation.
    ; Aucun deref ici : la fonction fait tout, on ne touche pas son retour.
    lwz   r3, apOpnC27@l(r11)
    lwz   r4, apOpnArg4@l(r11)
    lwz   r5, apOpnC28@l(r11)
    lwz   r6, apOpnC25@l(r11)
    lwz   r7, apOpnC26@l(r11)
    lwz   r8, apOpnHeap@l(r11)
    lis   r12, 0x03a4
    ori   r12, r12, 0x2b94
    mtctr r12
    bctrl
    lis   r11, apTick@ha
    stw   r3, apOpnR3@l(r11)
    li    r12, 7
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnFabrique:
    ; --- la fabrique brute, (*(*(r27+0x24)))[0x14](ce meme objet, r31, r28)
    lwz   r3, apOpnC27@l(r11)
    lwz   r3, 0x24(r3)
    lwz   r10, 0x0(r3)
    lwz   r0, 0x14(r10)
    mtctr r0
    ; apOpnHeap est desormais une ADRESSE BRUTE, pas un drapeau : 0 = tas
    ; nul (l'allocateur cherchera le courant), sinon le tas a essayer --
    ; le capture, la racine statique, celui du fil. Python en pose la
    ; valeur, donc on en essaie plusieurs sans relancer Cemu.
    lwz   r4, apOpnHeap@l(r11)
    lwz   r5, apOpnC28@l(r11)
    bctrl

apOpnGot:
    lis   r11, apTick@ha
    li    r12, 2
    stw   r12, apOpnPhase@l(r11)
    stw   r3, apOpnR3@l(r11)        ; ce que la fabrique a rendu

    ; NE PAS DEREFERENCER SANS VERIFIER. Si la fabrique refuse -- ecran deja
    ; ouvert, contexte incomplet -- elle rend 0, et `lwz r12, 0xc(r3)` juste
    ; apres deref zero. C'est la meme faute que la premiere version de
    ; apSubSpy, qui plantait au chargement d'une sauvegarde. Ici on s'arrete
    ; proprement : apOpnPhase reste a 2, apOpnR3 vaut 0, et le diagnostic le
    ; dit au lieu de tuer le jeu.
    cmpwi r3, 0
    beq   apOpnAfter

    ; s'arreter la si on ne bisecte que la fabrique
    lwz   r12, apOpnStep@l(r11)
    cmpwi r12, 1
    beq   apOpnAfter

    ; 2) l'ouverture : (*(r3+0xc))[0x4c](r3, r27, r31, r24, r28, r25, r26)
    ; Cemu se FERME quand le jeu plante : on ne peut donc rien relire apres
    ; coup. Chaque maillon est donc verifie avant d'etre suivi, et un maillon
    ; nul laisse apOpnPhase a une valeur qui le designe -- 5 pour la vtable,
    ; 6 pour l'entree 0x4c. Un refus devient lisible au lieu d'etre fatal.
    lwz   r12, 0xc(r3)
    cmpwi r12, 0
    beq   apOpnNoVtable
    lwz   r0, 0x4c(r12)
    cmpwi r0, 0
    beq   apOpnNoSlot

    li    r12, 3
    stw   r12, apOpnPhase@l(r11)
    lwz   r12, 0xc(r3)
    lwz   r0, 0x4c(r12)
    mtctr r0
    lwz   r9, apOpnC26@l(r11)
    lwz   r8, apOpnC25@l(r11)
    lwz   r7, apOpnC28@l(r11)
    lwz   r6, apOpnC24@l(r11)
    lwz   r5, apOpnC31@l(r11)
    lwz   r4, apOpnC27@l(r11)
    bctrl

    lis   r11, apTick@ha
    li    r12, 4
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnNoVtable:
    li    r12, 5
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnNoSlot:
    li    r12, 6
    stw   r12, apOpnPhase@l(r11)

apOpnAfter:
    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apOpnDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apOpnDone@l(r11)

apGetWinProbe6End:
    blr

apGetWinProbe7:                 ; 0x03607284, fonction 0x03607274
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetWin7@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin7@l(r11)
    stw   r0, apGetWinFrom7@l(r11)
    stw   r3, apGetWinThis7@l(r11)
    stw   r4, apGetWinR4_7@l(r11)
    stw   r5, apGetWinR5_7@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd7@l(r11)
    blr

apGetWinProbe8:                 ; 0x036072f4, fonction 0x036072e0
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetWin8@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin8@l(r11)
    stw   r0, apGetWinFrom8@l(r11)
    stw   r3, apGetWinThis8@l(r11)
    stw   r4, apGetWinR4_8@l(r11)
    stw   r5, apGetWinR5_8@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd8@l(r11)
    blr

apGetWinProbe9:                 ; 0x036073a0, fonction 0x03607390
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetWin9@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin9@l(r11)
    stw   r0, apGetWinFrom9@l(r11)
    stw   r3, apGetWinThis9@l(r11)
    stw   r4, apGetWinR4_9@l(r11)
    stw   r5, apGetWinR5_9@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd9@l(r11)
    blr

apGetWinProbe10:                 ; 0x03607424, fonction 0x03607414
    stw   r0, 0x14(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetWin10@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin10@l(r11)
    stw   r0, apGetWinFrom10@l(r11)
    stw   r3, apGetWinThis10@l(r11)
    stw   r4, apGetWinR4_10@l(r11)
    stw   r5, apGetWinR5_10@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd10@l(r11)
    blr

apGetWinProbe11:                 ; 0x036074cc, fonction 0x036074b8
    stw   r0, 0x1c(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetWin11@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin11@l(r11)
    stw   r0, apGetWinFrom11@l(r11)
    stw   r3, apGetWinThis11@l(r11)
    stw   r4, apGetWinR4_11@l(r11)
    stw   r5, apGetWinR5_11@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd11@l(r11)
    blr

apGetWinProbe12:                 ; 0x03607578, fonction 0x03607560
    stw   r0, 0x1c(r1)         ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetWin12@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin12@l(r11)
    stw   r0, apGetWinFrom12@l(r11)
    stw   r3, apGetWinThis12@l(r11)
    stw   r4, apGetWinR4_12@l(r11)
    stw   r5, apGetWinR5_12@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd12@l(r11)
    blr

0x03606ae8 = bla apGetWinProbe0
0x03606c74 = bla apGetWinProbe1
0x03606e2c = bla apGetWinProbe2
0x03606ee8 = bla apGetWinProbe3
0x03606f58 = bla apGetWinProbe4
0x036070a8 = bla apGetWinProbe5
0x03607220 = bla apGetWinProbe6
0x03607284 = bla apGetWinProbe7
0x036072f4 = bla apGetWinProbe8
0x036073a0 = bla apGetWinProbe9
0x03607424 = bla apGetWinProbe10
0x036074cc = bla apGetWinProbe11
0x03607578 = bla apGetWinProbe12

apGetDrvSpy:                     ; 0x03a3ec2c, pilote de la fenetre
    ; Au point d'ancrage le mflr a deja eu lieu et r3 a ete recopie dans r30
    ; sans etre detruit : les sept arguments sont tous encore vivants.
    stw   r0, 0x84(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetDrvN@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetDrvN@l(r11)
    stw   r0, apGetDrvFrom@l(r11)
    stw   r3, apGetDrvThis@l(r11)
    stw   r4, apGetDrvA4@l(r11)
    stw   r5, apGetDrvA5@l(r11)
    stw   r6, apGetDrvA6@l(r11)
    stw   r7, apGetDrvA7@l(r11)
    stw   r8, apGetDrvA8@l(r11)
    stw   r9, apGetDrvA9@l(r11)
    blr

0x03a3ec2c = bla apGetDrvSpy

; --- sondes du texte des panneaux de la fenetre d'obtention -------------

apGetTxtSpy0:                   ; 0x02fd01ac, avant bl 0x03082c70, dans 0x02fcf63c
    stw   r10, 0x8(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetTxtN0@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetTxtN0@l(r11)
    stw   r3, apGetTxtR3_0@l(r11)
    lwz   r12, 0x0(r4)
    stw   r12, apGetTxtW0_0@l(r11)
    lwz   r12, 0x4(r4)
    stw   r12, apGetTxtW1_0@l(r11)
    blr

apGetTxtSpy1:                   ; 0x02fd01cc, avant bl 0x03082d88, dans 0x02fcf63c
    stw   r11, 0x8(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetTxtN1@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetTxtN1@l(r11)
    stw   r3, apGetTxtR3_1@l(r11)
    lwz   r12, 0x0(r4)
    stw   r12, apGetTxtW0_1@l(r11)
    lwz   r12, 0x4(r4)
    stw   r12, apGetTxtW1_1@l(r11)
    blr

apGetTxtSpy2:                   ; 0x02fd0db8, avant bl 0x03083154, dans 0x02fd0ce4
    stw   r8, 0x28(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apGetTxtN2@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetTxtN2@l(r11)
    stw   r3, apGetTxtR3_2@l(r11)
    lwz   r12, 0x0(r4)
    stw   r12, apGetTxtW0_2@l(r11)
    lwz   r12, 0x4(r4)
    stw   r12, apGetTxtW1_2@l(r11)

    ; --- recopier 64 octets du texte pointe ------------------------------
    ; r3 est encore vivant (il porte l'argument du bl qui suit), donc on le
    ; sauve dans un champ DEDIE plutot que dans apS3, que les blocs d'appel
    ; per-frame utilisent deja.
    stw   r3, apGetTxtSaveR3@l(r11)
    lwz   r3, 0x0(r4)
    lwz   r12, 0x0(r3)
    stw   r12, apGetTxtB0@l(r11)
    lwz   r12, 0x4(r3)
    stw   r12, apGetTxtB1@l(r11)
    lwz   r12, 0x8(r3)
    stw   r12, apGetTxtB2@l(r11)
    lwz   r12, 0xc(r3)
    stw   r12, apGetTxtB3@l(r11)
    lwz   r12, 0x10(r3)
    stw   r12, apGetTxtB4@l(r11)
    lwz   r12, 0x14(r3)
    stw   r12, apGetTxtB5@l(r11)
    lwz   r12, 0x18(r3)
    stw   r12, apGetTxtB6@l(r11)
    lwz   r12, 0x1c(r3)
    stw   r12, apGetTxtB7@l(r11)
    lwz   r12, 0x20(r3)
    stw   r12, apGetTxtB8@l(r11)
    lwz   r12, 0x24(r3)
    stw   r12, apGetTxtB9@l(r11)
    lwz   r12, 0x28(r3)
    stw   r12, apGetTxtB10@l(r11)
    lwz   r12, 0x2c(r3)
    stw   r12, apGetTxtB11@l(r11)
    lwz   r12, 0x30(r3)
    stw   r12, apGetTxtB12@l(r11)
    lwz   r12, 0x34(r3)
    stw   r12, apGetTxtB13@l(r11)
    lwz   r12, 0x38(r3)
    stw   r12, apGetTxtB14@l(r11)
    lwz   r12, 0x3c(r3)
    stw   r12, apGetTxtB15@l(r11)
    lwz   r3, apGetTxtSaveR3@l(r11)

    ; --- substituer notre texte, si demande ------------------------------
    lwz   r12, apGetTxtReq@l(r11)
    cmpwi r12, 0
    beq   apGetTxtSpy2End
    li    r12, 0
    stw   r12, apGetTxtReq@l(r11)      ; un coup, pas un mode : un client mort
                                       ; ne laisse pas la fenetre detournee
    lis   r12, apGetTxtOur@ha
    addi  r12, r12, apGetTxtOur@l
    stw   r12, 0x0(r4)
    lwz   r12, apGetTxtDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetTxtDone@l(r11)
apGetTxtSpy2End:
    blr

0x02fd01ac = bla apGetTxtSpy0
0x02fd01cc = bla apGetTxtSpy1
0x02fd0db8 = bla apGetTxtSpy2

apResSpy:                        ; 0x03082c8c, entree de 0x03082c70
    ; r3/r4/r5 sont encore les arguments : r3 n'est recopie qu'en 0x03082c90.
    ; r4 est la SafeString du libelle -- son premier mot est le const char*.
    stw   r0, 0x24(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apResN@l(r11)
    addi  r12, r12, 1
    stw   r12, apResN@l(r11)
    lwz   r12, apResArm@l(r11)
    cmpwi r12, 0
    beq   apResEnd
    cmpwi r12, 4
    beq   apResSlot0
    cmpwi r12, 3
    beq   apResSlot1
    cmpwi r12, 2
    beq   apResSlot2
    cmpwi r12, 1
    beq   apResSlot3
    b     apResEnd
apResSlot0:
    stw   r0, apResRet0@l(r11)
    stw   r3, apResA0@l(r11)
    stw   r4, apResB0@l(r11)
    stw   r5, apResC0@l(r11)
    stw   r3, apResSaveR3@l(r11)
    lwz   r3, 0x0(r4)
    lwz   r12, 0x0(r3)
    stw   r12, apResL0_0@l(r11)
    lwz   r12, 0x4(r3)
    stw   r12, apResL0_1@l(r11)
    lwz   r12, 0x8(r3)
    stw   r12, apResL0_2@l(r11)
    lwz   r12, 0xc(r3)
    stw   r12, apResL0_3@l(r11)
    lwz   r12, 0x10(r3)
    stw   r12, apResL0_4@l(r11)
    lwz   r12, 0x14(r3)
    stw   r12, apResL0_5@l(r11)
    lwz   r12, 0x18(r3)
    stw   r12, apResL0_6@l(r11)
    lwz   r12, 0x1c(r3)
    stw   r12, apResL0_7@l(r11)
    lwz   r3, apResSaveR3@l(r11)
    lwz   r12, apResArm@l(r11)
    addi  r12, r12, -1
    stw   r12, apResArm@l(r11)
    b     apResEnd
apResSlot1:
    stw   r0, apResRet1@l(r11)
    stw   r3, apResA1@l(r11)
    stw   r4, apResB1@l(r11)
    stw   r5, apResC1@l(r11)
    stw   r3, apResSaveR3@l(r11)
    lwz   r3, 0x0(r4)
    lwz   r12, 0x0(r3)
    stw   r12, apResL1_0@l(r11)
    lwz   r12, 0x4(r3)
    stw   r12, apResL1_1@l(r11)
    lwz   r12, 0x8(r3)
    stw   r12, apResL1_2@l(r11)
    lwz   r12, 0xc(r3)
    stw   r12, apResL1_3@l(r11)
    lwz   r12, 0x10(r3)
    stw   r12, apResL1_4@l(r11)
    lwz   r12, 0x14(r3)
    stw   r12, apResL1_5@l(r11)
    lwz   r12, 0x18(r3)
    stw   r12, apResL1_6@l(r11)
    lwz   r12, 0x1c(r3)
    stw   r12, apResL1_7@l(r11)
    lwz   r3, apResSaveR3@l(r11)
    lwz   r12, apResArm@l(r11)
    addi  r12, r12, -1
    stw   r12, apResArm@l(r11)
    b     apResEnd
apResSlot2:
    stw   r0, apResRet2@l(r11)
    stw   r3, apResA2@l(r11)
    stw   r4, apResB2@l(r11)
    stw   r5, apResC2@l(r11)
    stw   r3, apResSaveR3@l(r11)
    lwz   r3, 0x0(r4)
    lwz   r12, 0x0(r3)
    stw   r12, apResL2_0@l(r11)
    lwz   r12, 0x4(r3)
    stw   r12, apResL2_1@l(r11)
    lwz   r12, 0x8(r3)
    stw   r12, apResL2_2@l(r11)
    lwz   r12, 0xc(r3)
    stw   r12, apResL2_3@l(r11)
    lwz   r12, 0x10(r3)
    stw   r12, apResL2_4@l(r11)
    lwz   r12, 0x14(r3)
    stw   r12, apResL2_5@l(r11)
    lwz   r12, 0x18(r3)
    stw   r12, apResL2_6@l(r11)
    lwz   r12, 0x1c(r3)
    stw   r12, apResL2_7@l(r11)
    lwz   r3, apResSaveR3@l(r11)
    lwz   r12, apResArm@l(r11)
    addi  r12, r12, -1
    stw   r12, apResArm@l(r11)
    b     apResEnd
apResSlot3:
    stw   r0, apResRet3@l(r11)
    stw   r3, apResA3@l(r11)
    stw   r4, apResB3@l(r11)
    stw   r5, apResC3@l(r11)
    stw   r3, apResSaveR3@l(r11)
    lwz   r3, 0x0(r4)
    lwz   r12, 0x0(r3)
    stw   r12, apResL3_0@l(r11)
    lwz   r12, 0x4(r3)
    stw   r12, apResL3_1@l(r11)
    lwz   r12, 0x8(r3)
    stw   r12, apResL3_2@l(r11)
    lwz   r12, 0xc(r3)
    stw   r12, apResL3_3@l(r11)
    lwz   r12, 0x10(r3)
    stw   r12, apResL3_4@l(r11)
    lwz   r12, 0x14(r3)
    stw   r12, apResL3_5@l(r11)
    lwz   r12, 0x18(r3)
    stw   r12, apResL3_6@l(r11)
    lwz   r12, 0x1c(r3)
    stw   r12, apResL3_7@l(r11)
    lwz   r3, apResSaveR3@l(r11)
    lwz   r12, apResArm@l(r11)
    addi  r12, r12, -1
    stw   r12, apResArm@l(r11)
    b     apResEnd
apResEnd:
    blr

0x03082c8c = bla apResSpy

apSubSpy:                        ; 0x030835c8, juste apres bl 0x03082c70
    ; r3 est la valeur de retour du resolveur : le texte de <acteur>_Name.
    lwz   r28, 0x278(r1)        ; origine
    lis   r11, apTick@ha
    stw   r1, apR1Name@l(r11)       ; pile ou la fenetre construit son texte
    lwz   r12, apSubN@l(r11)
    addi  r12, r12, 1
    stw   r12, apSubN@l(r11)
    stw   r3, apSubOut@l(r11)

    ; MESURE : au retour, r3 vaut 0. Le resolveur ne RENVOIE donc pas le
    ; texte -- il l'ecrit dans le tampon que l'appelant lui passe en r3, soit
    ; 0x60(r1) ici (releve : sortie = 0x0e200890, et r1 = 0x0e200830).
    ;
    ; On lit donc la PILE, pas r3. C'est sur par construction : r1 est
    ; toujours un pointeur de pile valide, la ou r3 pouvait etre nul -- ce qui
    ; a fait planter le jeu au chargement d'une sauvegarde.
    ; MESURE : 0x60(r1) contient une chaine a stockage interne dont les
    ; donnees commencent par "Acto" -- c'est le CHEMIN D'ARCHIVE, pas la
    ; sortie. Les trois arguments sont donc (archive, libelle, sortie) et non
    ; (sortie, libelle, archive) comme le desassemblage me l'avait fait lire.
    lwz   r12, 0x60(r1)
    stw   r12, apSubW0@l(r11)
    lwz   r12, 0x64(r1)
    stw   r12, apSubW1@l(r11)
    lwz   r12, 0x68(r1)
    stw   r12, apSubW2@l(r11)
    lwz   r12, 0x6c(r1)
    stw   r12, apSubW3@l(r11)

    ; La vraie sortie est r5, et r5 est volatil -- detruit par l'appel. Mais
    ; elle vient de r29, non volatil, dont la restauration n'a lieu qu'a
    ; 0x030835cc : une instruction APRES notre ancrage. r29 la porte donc
    ; encore. Et le derefencer est sur : si l'on est ici, c'est que le
    ; resolveur vient d'ecrire dedans.
    stw   r4, apSubSaveR4@l(r11)
    mr    r4, r29
    stw   r4, apSubOutBuf@l(r11)
    lwz   r12, 0x0(r4)
    stw   r12, apSubO0@l(r11)
    lwz   r12, 0x4(r4)
    stw   r12, apSubO1@l(r11)
    lwz   r12, 0x8(r4)
    stw   r12, apSubO2@l(r11)
    lwz   r12, 0xc(r4)
    stw   r12, apSubO3@l(r11)
    lwz   r12, 0x10(r4)
    stw   r12, apSubO4@l(r11)
    lwz   r12, 0x14(r4)
    stw   r12, apSubO5@l(r11)
    lwz   r12, 0x18(r4)
    stw   r12, apSubO6@l(r11)
    lwz   r12, 0x1c(r4)
    stw   r12, apSubO7@l(r11)
    lwz   r4, apSubSaveR4@l(r11)

    ; --- substitution, si demandee --------------------------------------
    ; MESURE : la sortie est le couple { const char16_t*, longueur en unites },
    ; releve { 0x21c541ec, 17 } pour 'Opale brute' -- 18 unites au MSBT,
    ; terminateur exclu. Le meme couple que la boite de dialogue.
    ;
    ; apSubReq est un COMPTE, pas un booleen : la fenetre resout _Name deux
    ; fois, et un client mort cesse de le renouveler. Deux ecritures, aucun
    ; appel : c'est ce qui rend cette voie sure la ou rejouer l'ouvreur
    ; d'ecran plantait.
    lwz   r12, apSubReq@l(r11)
    cmpwi r12, 0
    beq   apSubEnd
    addi  r12, r12, -1
    stw   r12, apSubReq@l(r11)

    stw   r4, apSubSaveR4@l(r11)
    mr    r4, r29
    lis   r12, apSubBuf@ha
    addi  r12, r12, apSubBuf@l
    stw   r12, 0x0(r4)
    lwz   r12, apSubLen@l(r11)
    stw   r12, 0x4(r4)
    lwz   r4, apSubSaveR4@l(r11)

    lwz   r12, apSubDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apSubDone@l(r11)
apSubEnd:
    blr

0x030835c8 = bla apSubSpy

apSubDescSpy:                    ; 0x03083860, juste apres bl 0x03082c70
    ; ATTENTION A L'ORDRE : ici l'instruction d'origine restaure r29, donc
    ; tout le travail se fait AVANT, et la rejouee vient en dernier.
    lis   r11, apTick@ha
    lwz   r12, apSubDescN@l(r11)
    addi  r12, r12, 1
    stw   r12, apSubDescN@l(r11)

    lwz   r12, apSubDescReq@l(r11)
    cmpwi r12, 0
    beq   apSubDescOrig
    addi  r12, r12, -1
    stw   r12, apSubDescReq@l(r11)
    lis   r12, apSubDescBuf@ha
    addi  r12, r12, apSubDescBuf@l
    stw   r12, 0x0(r29)
    lwz   r12, apSubDescLen@l(r11)
    stw   r12, 0x4(r29)
    lwz   r12, apSubDescDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apSubDescDone@l(r11)

apSubDescOrig:
    ; ORIGINE : lmw r27, 0x22c(r1), rejouee en cinq chargements
    lwz   r27, 0x22c(r1)
    lwz   r28, 0x230(r1)
    lwz   r29, 0x234(r1)
    lwz   r30, 0x238(r1)
    lwz   r31, 0x23c(r1)
    blr

0x03083860 = bla apSubDescSpy

apShowSpy:                       ; 0x03a40d38, prologue de 0x03a40d20
    ; La mise en scene, a la source. Ancree sur le `stw r0, 0x1c(r1)` qui
    ; sauve LR : r0 porte encore l'appelant, et ni r3 ni r4 n'ont ete
    ; detruits -- le `mr r29, r3` est en 0x03a40d3c, apres l'ancre.
    ;   r3 = l'ecran      r4 = le MODE, 0 a 4
    stw   r0, 0x1c(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apShowN@l(r11)
    addi  r12, r12, 1
    stw   r12, apShowN@l(r11)
    lwz   r12, apShowT6@l(r11)
    stw   r12, apShowT7@l(r11)
    lwz   r12, apShowM6@l(r11)
    stw   r12, apShowM7@l(r11)
    lwz   r12, apShowL6@l(r11)
    stw   r12, apShowL7@l(r11)
    lwz   r12, apShowT5@l(r11)
    stw   r12, apShowT6@l(r11)
    lwz   r12, apShowM5@l(r11)
    stw   r12, apShowM6@l(r11)
    lwz   r12, apShowL5@l(r11)
    stw   r12, apShowL6@l(r11)
    lwz   r12, apShowT4@l(r11)
    stw   r12, apShowT5@l(r11)
    lwz   r12, apShowM4@l(r11)
    stw   r12, apShowM5@l(r11)
    lwz   r12, apShowL4@l(r11)
    stw   r12, apShowL5@l(r11)
    lwz   r12, apShowT3@l(r11)
    stw   r12, apShowT4@l(r11)
    lwz   r12, apShowM3@l(r11)
    stw   r12, apShowM4@l(r11)
    lwz   r12, apShowL3@l(r11)
    stw   r12, apShowL4@l(r11)
    lwz   r12, apShowT2@l(r11)
    stw   r12, apShowT3@l(r11)
    lwz   r12, apShowM2@l(r11)
    stw   r12, apShowM3@l(r11)
    lwz   r12, apShowL2@l(r11)
    stw   r12, apShowL3@l(r11)
    lwz   r12, apShowT1@l(r11)
    stw   r12, apShowT2@l(r11)
    lwz   r12, apShowM1@l(r11)
    stw   r12, apShowM2@l(r11)
    lwz   r12, apShowL1@l(r11)
    stw   r12, apShowL2@l(r11)
    lwz   r12, apShowT0@l(r11)
    stw   r12, apShowT1@l(r11)
    lwz   r12, apShowM0@l(r11)
    stw   r12, apShowM1@l(r11)
    lwz   r12, apShowL0@l(r11)
    stw   r12, apShowL1@l(r11)
    stw   r3, apShowT0@l(r11)
    stw   r4, apShowM0@l(r11)
    stw   r0, apShowL0@l(r11)
    blr

0x03a40d38 = bla apShowSpy

apUpSpy:                         ; 0x0308070c, prologue de 0x030806f0
    ; L'etage au-dessus de 0x03a42b94 : c'est lui qui, l'ecran construit,
    ; fait le reste de la mise en scene. Cinq arguments.
    stw   r0, 0x2c(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apUpN@l(r11)
    addi  r12, r12, 1
    stw   r12, apUpN@l(r11)
    stw   r0, apUpLr@l(r11)
    stw   r1, apUpR1@l(r11)
    stw   r3, apUpA1@l(r11)
    stw   r4, apUpA2@l(r11)
    stw   r5, apUpA3@l(r11)
    stw   r6, apUpA4@l(r11)
    stw   r7, apUpA5@l(r11)
    blr

0x0308070c = bla apUpSpy

apOpnProSpy:                     ; 0x03a42bb8, prologue de 0x03a42b94
    ; Ancree sur le `stw r0, 0x34(r1)` qui sauve LR : r0 porte encore
    ; l'adresse de retour, et les six `mr` du prologue ont RECOPIE r3..r8
    ; sans les detruire. Les six arguments sont donc tous vivants ici --
    ; c'est le seul point du corps ou c'est vrai.
    ;   r3 -> r27 (gestionnaire)   r4 -> r30      r5 -> r28 (index)
    ;   r6 -> r25                  r7 -> r26      r8 -> r31 (LE TAS)
    stw   r0, 0x34(r1)          ; origine
    lis   r11, apTick@ha
    lwz   r12, apOpnProN@l(r11)
    addi  r12, r12, 1
    stw   r12, apOpnProN@l(r11)
    stw   r0, apOpnProLr@l(r11)
    stw   r1, apOpnProR1@l(r11)
    stw   r3, apOpnProA1@l(r11)
    stw   r4, apOpnProA2@l(r11)
    stw   r5, apOpnProA3@l(r11)
    stw   r6, apOpnProA4@l(r11)
    stw   r7, apOpnProA5@l(r11)
    stw   r8, apOpnProA6@l(r11)
    ; derouler la pile ICI : la chaine qui mene a l'affichage
    stw   r1, apWStkF@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL0@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL1@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL2@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL3@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL4@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL5@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL6@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL7@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL8@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL9@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL10@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL11@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL12@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL13@l(r11)
apWStkEnd:
    blr

0x03a42bb8 = bla apOpnProSpy

apOpnSpy:                        ; 0x03a42ce8, juste apres la fabrique
    ; r3 est l'objet ecran que la fabrique vient de rendre ; r24-r28 et r31
    ; portent les arguments que le second appel va recevoir.
    mr    r29, r3               ; origine
    lis   r11, apTick@ha
    stw   r1, apR1Opn@l(r11)        ; pile du VRAI site d'ouverture
    lwz   r12, apOpnN@l(r11)
    addi  r12, r12, 1
    stw   r12, apOpnN@l(r11)
    stw   r3, apOpnThis@l(r11)
    stw   r24, apOpn24@l(r11)
    stw   r25, apOpn25@l(r11)
    stw   r26, apOpn26@l(r11)
    stw   r27, apOpn27@l(r11)
    stw   r28, apOpn28@l(r11)
    stw   r31, apOpn31@l(r11)
    blr

0x03a42ce8 = bla apOpnSpy

"""Wire ingress and egress codec."""

from __future__ import annotations

import dataclasses as _dataclasses
import types as _types
import typing as _typing

_PUBLIC_TYPE_TAGS: dict[str, str] = {
    "span.core.model.administration.InitializeRepositoryRequest": "InitializeRepositoryRequest",
    "span.core.model.administration.InitializeRepositoryResult": "InitializeRepositoryResult",
    "span.core.model.answers.AmbiguousSurface": "AmbiguousSurface",
    "span.core.model.answers.Answer": "Answer",
    "span.core.model.answers.AnswerGroup": "AnswerGroup",
    "span.core.model.answers.Challenged": "Challenged",
    "span.core.model.answers.Changed": "Changed",
    "span.core.model.answers.ChangedConclusion": "ChangedConclusion",
    "span.core.model.answers.ChangedSurface": "ChangedSurface",
    "span.core.model.answers.ConclusionView": "ConclusionView",
    "span.core.model.answers.EvidencePage": "EvidencePage",
    "span.core.model.answers.Gap": "Gap",
    "span.core.model.answers.HistoricalConclusion": "HistoricalConclusion",
    "span.core.model.answers.Rejected": "Rejected",
    "span.core.model.answers.SurfaceDeclared": "SurfaceDeclared",
    "span.core.model.answers.Unavailable": "Unavailable",
    "span.core.model.answers.VerificationView": "VerificationView",
    "span.core.model.claims.CapabilityMembershipValue": "CapabilityMembershipValue",
    "span.core.model.claims.ConfigurationEnvironmentValue": "ConfigurationEnvironmentValue",
    "span.core.model.claims.ExecutedVerification": "ExecutedVerification",
    "span.core.model.claims.InvariantConstraintValue": "InvariantConstraintValue",
    "span.core.model.claims.LifecycleStateValue": "LifecycleStateValue",
    "span.core.model.claims.OwnershipCustodyValue": "OwnershipCustodyValue",
    "span.core.model.claims.PurposeValue": "PurposeValue",
    "span.core.model.claims.RecordedConflict": "RecordedConflict",
    "span.core.model.claims.RepresentationContractValue": "RepresentationContractValue",
    "span.core.model.claims.ResponsibilityValue": "ResponsibilityValue",
    "span.core.model.claims.SemanticClaim": "SemanticClaim",
    "span.core.model.claims.SemanticConflict": "SemanticConflict",
    "span.core.model.claims.SemanticRelationship": "SemanticRelationship",
    "span.core.model.claims.TransformationOwnershipValue": "TransformationOwnershipValue",
    "span.core.model.claims.VerificationRecord": "VerificationRecord",
    "span.core.model.claims.VerificationStatus": "VerificationStatus",
    "span.core.model.claims.VerificationValue": "VerificationValue",
    "span.core.model.commands.AskRequest": "AskRequest",
    "span.core.model.commands.ChallengeConclusionRef": "ChallengeConclusionRef",
    "span.core.model.commands.ChallengeRaise": "ChallengeRaise",
    "span.core.model.commands.ConclusionContentDraft": "ConclusionContentDraft",
    "span.core.model.commands.ConfirmConclusion": "ConfirmConclusion",
    "span.core.model.commands.ContextBoundTarget": "context_bound",
    "span.core.model.commands.CorrectConclusion": "CorrectConclusion",
    "span.core.model.commands.CreateChallengeCommand": "create_challenge",
    "span.core.model.commands.CreateUnderstandingCommand": "create_understanding",
    "span.core.model.commands.ExplicitTarget": "explicit",
    "span.core.model.commands.GapDraft": "GapDraft",
    "span.core.model.commands.ProposedConclusion": "ProposedConclusion",
    "span.core.model.commands.ReconsiderRequest": "ReconsiderRequest",
    "span.core.model.commands.RecordVerificationCommand": "record_verification",
    "span.core.model.commands.ReplaceConclusion": "ReplaceConclusion",
    "span.core.model.commands.ResolvedChallengeDisposition": "resolved",
    "span.core.model.commands.StartContextRequest": "StartContextRequest",
    "span.core.model.commands.UnresolvedChallengeDisposition": "unresolved",
    "span.core.model.commands.UpdateUnderstandingCommand": "update_understanding",
    "span.core.model.commands.WithdrawConclusion": "WithdrawConclusion",
    "span.core.model.investigation.AdmittedEvidence": "AdmittedEvidence",
    "span.core.model.investigation.AlreadyAdmittedEvidence": "AlreadyAdmittedEvidence",
    "span.core.model.investigation.DiscoveryObservation": "DiscoveryObservation",
    "span.core.model.investigation.EvidenceAdmissionResult": "EvidenceAdmissionResult",
    "span.core.model.investigation.EvidenceAdmissionView": "EvidenceAdmissionView",
    "span.core.model.investigation.EvidenceDelivery": "EvidenceDelivery",
    "span.core.model.investigation.EvidenceExtendRequest": "EvidenceExtendRequest",
    "span.core.model.investigation.EvidenceRequest": "EvidenceRequest",
    "span.core.model.investigation.EvidenceSourceFailure": "EvidenceSourceFailure",
    "span.core.model.investigation.EvidenceStartRequest": "EvidenceStartRequest",
    "span.core.model.investigation.InvestigationContext": "InvestigationContext",
    "span.core.model.investigation.InvestigationContextRef": "InvestigationContextRef",
    "span.core.model.investigation.LifecycleRetention": "LifecycleRetention",
    "span.core.model.investigation.OmittedEvidence": "OmittedEvidence",
    "span.core.model.investigation.SourceObservation": "SourceObservation",
    "span.core.model.investigation.SourceRange": "SourceRange",
    "span.core.model.outcomes.ChallengeRecorded": "ChallengeRecorded",
    "span.core.model.outcomes.UnderstandingRecorded": "UnderstandingRecorded",
    "span.core.model.outcomes.VerificationRecorded": "VerificationRecorded",
    "span.core.model.primitives.AnswerId": "AnswerId",
    "span.core.model.primitives.AuthorityApplicability": "AuthorityApplicability",
    "span.core.model.primitives.AuthorityBinding": "AuthorityBinding",
    "span.core.model.primitives.AuthoritySupport": "AuthoritySupport",
    "span.core.model.primitives.BoundInfo": "BoundInfo",
    "span.core.model.primitives.CandidateAuthority": "CandidateAuthority",
    "span.core.model.primitives.ChallengeId": "ChallengeId",
    "span.core.model.primitives.ChallengeRevision": "ChallengeRevision",
    "span.core.model.primitives.ClaimId": "ClaimId",
    "span.core.model.primitives.ClaimRef": "claim",
    "span.core.model.primitives.ConclusionId": "ConclusionId",
    "span.core.model.primitives.ConclusionRevisionNumber": "ConclusionRevisionNumber",
    "span.core.model.primitives.ConclusionRevisionRef": "ConclusionRevisionRef",
    "span.core.model.primitives.DeclaredPrecedence": "DeclaredPrecedence",
    "span.core.model.primitives.DiscoveryObservationId": "DiscoveryObservationId",
    "span.core.model.primitives.EvidenceId": "EvidenceId",
    "span.core.model.primitives.EvidenceIdRef": "EvidenceIdRef",
    "span.core.model.primitives.EvidenceRef": "evidence",
    "span.core.model.primitives.EvidenceScope": "EvidenceScope",
    "span.core.model.primitives.Freshness": "Freshness",
    "span.core.model.primitives.FreshnessItem": "FreshnessItem",
    "span.core.model.primitives.HandleLifespan": "HandleLifespan",
    "span.core.model.primitives.ImpactItem": "ImpactItem",
    "span.core.model.primitives.InvestigationContextId": "InvestigationContextId",
    "span.core.model.primitives.ProposedChange": "ProposedChange",
    "span.core.model.primitives.QueryBounds": "QueryBounds",
    "span.core.model.primitives.RelationshipId": "RelationshipId",
    "span.core.model.primitives.RelationshipRef": "relationship",
    "span.core.model.primitives.RequestId": "RequestId",
    "span.core.model.primitives.SemanticBasis": "SemanticBasis",
    "span.core.model.primitives.ServiceBoundsPolicy": "ServiceBoundsPolicy",
    "span.core.model.primitives.SourceObservationId": "SourceObservationId",
    "span.core.model.primitives.Subject": "Subject",
    "span.core.model.primitives.SubjectCandidate": "SubjectCandidate",
    "span.core.model.primitives.SubjectId": "SubjectId",
    "span.core.model.primitives.SubjectResolution": "SubjectResolution",
    "span.core.model.primitives.SubjectSelector": "SubjectSelector",
    "span.core.model.primitives.UnderstandingId": "UnderstandingId",
    "span.core.model.primitives.UnderstandingVersionNumber": "UnderstandingVersionNumber",
    "span.core.model.primitives.VerificationRunId": "VerificationRunId",
    "span.core.model.recording.ContentDigest": "ContentDigest",
    "span.core.model.recording.ReceiptDecision": "ReceiptDecision",
    "span.core.model.recording.RecordingIdentity": "RecordingIdentity",
    "span.core.model.recording.RecordingKey": "RecordingKey",
    "span.core.model.recording.RecordReceipt": "RecordReceipt",
    "span.core.model.recording.RequestBinding": "RequestBinding",
    "span.core.model.repository.EvidenceInventoryItem": "EvidenceInventoryItem",
    "span.core.model.repository.EvidenceInventoryPage": "EvidenceInventoryPage",
    "span.core.model.repository.EvidenceLineRange": "EvidenceLineRange",
    "span.core.model.repository.EvidenceSelection": "EvidenceSelection",
    "span.core.model.repository.EvidenceUnit": "EvidenceUnit",
    "span.core.model.repository.RepositoryIdentity": "RepositoryIdentity",
    "span.core.model.repository.RepositoryState": "RepositoryState",
    "span.core.model.repository.StructuralEdge": "StructuralEdge",
    "span.core.model.repository.StructuralFreshnessReport": "StructuralFreshnessReport",
    "span.core.model.repository.StructuralLocateEntry": "StructuralLocateEntry",
    "span.core.model.repository.StructuralLocateResult": "StructuralLocateResult",
    "span.core.model.repository.StructuralLocation": "StructuralLocation",
    "span.core.model.repository.StructuralNeighborsResult": "StructuralNeighborsResult",
    "span.core.model.repository.StructuralObservation": "StructuralObservation",
    "span.core.model.repository.StructuralOutlineEntry": "StructuralOutlineEntry",
    "span.core.model.repository.StructuralReachNode": "StructuralReachNode",
    "span.core.model.repository.StructuralResult": "StructuralResult",
    "span.core.model.repository.StructuralSearchHit": "StructuralSearchHit",
    "span.core.model.support.AuthoritySupportDependency": "AuthoritySupportDependency",
    "span.core.model.support.ConclusionQualification": "ConclusionQualification",
    "span.core.model.support.ConclusionSupport": "ConclusionSupport",
    "span.core.model.support.DependencyFinding": "DependencyFinding",
    "span.core.model.support.DiscoverySupport": "DiscoverySupport",
    "span.core.model.support.ObservationQualification": "ObservationQualification",
    "span.core.model.support.ObservationSupport": "ObservationSupport",
    "span.core.model.support.PremiseSupport": "PremiseSupport",
    "span.core.model.support.SourceSupport": "SourceSupport",
    "span.core.model.support.SupportEvaluation": "SupportEvaluation",
    "span.core.model.support.SupportQualification": "SupportQualification",
    "span.core.model.support.SupportUnavailable": "SupportUnavailable",
    "span.core.model.support.UnderstandingQualification": "UnderstandingQualification",
    "span.core.model.support.UnderstandingSupport": "UnderstandingSupport",
    "span.core.model.support.VerificationQualification": "VerificationQualification",
    "span.core.model.support.VerificationSupport": "VerificationSupport",
    "span.core.model.support.VerificationSupportRequest": "VerificationSupportRequest",
    "span.core.model.surfaces.StaleConclusionRef": "StaleConclusionRef",
    "span.core.model.surfaces.Surface": "Surface",
    "span.core.model.surfaces.SurfaceBoundary": "SurfaceBoundary",
    "span.core.model.surfaces.SurfaceKey": "SurfaceKey",
    "span.core.model.surfaces.SurfaceReference": "SurfaceReference",
    "span.core.model.surfaces.SurfaceStatus": "SurfaceStatus",
    "span.core.model.surfaces.SurfaceStatusUnavailable": "SurfaceStatusUnavailable",
    "span.core.model.understanding.Challenge": "Challenge",
    "span.core.model.understanding.ChallengeResolution": "ChallengeResolution",
    "span.core.model.understanding.ConclusionRevision": "ConclusionRevision",
    "span.core.model.understanding.ContextRetrievalSelector": "ContextRetrievalSelector",
    "span.core.model.understanding.CurrentUnderstandingSelector": "CurrentUnderstandingSelector",
    "span.core.model.understanding.ReassessRequest": "ReassessRequest",
    "span.core.model.understanding.ReceiptRetrievalSelector": "ReceiptRetrievalSelector",
    "span.core.model.understanding.RecordedQuestionGap": "RecordedQuestionGap",
    "span.core.model.understanding.RecordedQuestionSelector": "RecordedQuestionSelector",
    "span.core.model.understanding.ResolvedChallengeRecord": "ResolvedChallengeRecord",
    "span.core.model.understanding.RetrievedContext": "RetrievedContext",
    "span.core.model.understanding.RetrievedReceipt": "RetrievedReceipt",
    "span.core.model.understanding.RetrievedUnderstanding": "RetrievedUnderstanding",
    "span.core.model.understanding.SupportedConclusion": "SupportedConclusion",
    "span.core.model.understanding.Understanding": "Understanding",
    "span.core.model.understanding.UnderstandingSnapshotSelector": "UnderstandingSnapshotSelector",
    "span.core.model.understanding.UnderstandingVersion": "UnderstandingVersion",
    "span.core.model.understanding.UnresolvedChallengeRecord": "UnresolvedChallengeRecord",
    "span.core.model.understanding.WithdrawnConclusion": "WithdrawnConclusion",
    "span.core.model.verification.ProposedVerificationRun": "ProposedVerificationRun",
    "span.core.model.verification.VerificationRun": "VerificationRun",
    "span.core.model.verification.VerificationScope": "VerificationScope",
    "span.core.schema.record_wire.AddConclusionWire": "AddConclusion",
    "span.core.schema.record_wire.AdmittedDiscoverySupportWire": "admitted_discovery",
    "span.core.schema.record_wire.AdmittedSourceSupportWire": "admitted_source",
    "span.core.schema.record_wire.AuthoritySupportWire": "authority",
    "span.core.schema.record_wire.ConclusionRefWire": "ConclusionRef",
    "span.core.schema.record_wire.ConfirmConclusionWire": "ConfirmConclusion",
    "span.core.schema.record_wire.CorrectConclusionWire": "CorrectConclusion",
    "span.core.schema.record_wire.DiscoveryBoundarySupportWire": "discovery",
    "span.core.schema.record_wire.DiscoveryScopeWire": "DiscoveryScope",
    "span.core.schema.record_wire.GapWire": "GapInput",
    "span.core.schema.record_wire.IdentityWire": "IdentityInput",
    "span.core.schema.record_wire.PremiseSupportWire": "premise",
    "span.core.schema.record_wire.RangeWire": "Range",
    "span.core.schema.record_wire.RecordActionsWire": "RecordActions",
    "span.core.schema.record_wire.RecordRequestWire": "RecordRequest",
    "span.core.schema.record_wire.RecordWireResolver": "RecordWireResolver",
    "span.core.schema.record_wire.ReplaceActionWire": "ReplaceConclusion",
    "span.core.schema.record_wire.ResolvedDispositionWire": "resolved",
    "span.core.schema.record_wire.SourceSupportWire": "source",
    "span.core.schema.record_wire.SurfaceBoundaryWire": "SurfaceBoundaryInput",
    "span.core.schema.record_wire.SurfaceKeyWire": "SurfaceKeyInput",
    "span.core.schema.record_wire.SurfaceWire": "SurfaceInput",
    "span.core.schema.record_wire.UnresolvedDispositionWire": "unresolved",
    "span.core.schema.record_wire.VerificationRunWire": "VerificationRunInput",
    "span.core.schema.record_wire.WithdrawActionWire": "WithdrawConclusion",
    "span.shell.mcp.models.ServiceContext": "ServiceContext",
    "span.shell.mcp.models.ToolError": "ToolError",
    "span.shell.mcp.models.ToolResult": "ToolResult",
}

_PUBLIC_SCHEMA_NAMES: dict[str, str] = {
    "span.core.model.administration.InitializeRepositoryRequest": "InitializeRepositoryRequest",
    "span.core.model.administration.InitializeRepositoryResult": "InitializeRepositoryResult",
    "span.core.model.answers.AmbiguousSurface": "AmbiguousSurface",
    "span.core.model.answers.Answer": "Answer",
    "span.core.model.answers.AnswerGroup": "AnswerGroup",
    "span.core.model.answers.Challenged": "Challenged",
    "span.core.model.answers.Changed": "Changed",
    "span.core.model.answers.ChangedConclusion": "ChangedConclusion",
    "span.core.model.answers.ChangedSurface": "ChangedSurface",
    "span.core.model.answers.ConclusionView": "ConclusionView",
    "span.core.model.answers.EvidencePage": "EvidencePage",
    "span.core.model.answers.Gap": "Gap",
    "span.core.model.answers.HistoricalConclusion": "HistoricalConclusion",
    "span.core.model.answers.Rejected": "Rejected",
    "span.core.model.answers.SurfaceDeclared": "SurfaceDeclared",
    "span.core.model.answers.Unavailable": "Unavailable",
    "span.core.model.answers.VerificationView": "VerificationView",
    "span.core.model.claims.CapabilityMembershipValue": "CapabilityMembershipValue",
    "span.core.model.claims.ConfigurationEnvironmentValue": "ConfigurationEnvironmentValue",
    "span.core.model.claims.ExecutedVerification": "ExecutedVerification",
    "span.core.model.claims.InvariantConstraintValue": "InvariantConstraintValue",
    "span.core.model.claims.LifecycleStateValue": "LifecycleStateValue",
    "span.core.model.claims.OwnershipCustodyValue": "OwnershipCustodyValue",
    "span.core.model.claims.PurposeValue": "PurposeValue",
    "span.core.model.claims.RecordedConflict": "RecordedConflict",
    "span.core.model.claims.RepresentationContractValue": "RepresentationContractValue",
    "span.core.model.claims.ResponsibilityValue": "ResponsibilityValue",
    "span.core.model.claims.SemanticClaim": "SemanticClaim",
    "span.core.model.claims.SemanticConflict": "SemanticConflict",
    "span.core.model.claims.SemanticRelationship": "SemanticRelationship",
    "span.core.model.claims.TransformationOwnershipValue": "TransformationOwnershipValue",
    "span.core.model.claims.VerificationRecord": "VerificationRecord",
    "span.core.model.claims.VerificationStatus": "VerificationStatus",
    "span.core.model.claims.VerificationValue": "VerificationValue",
    "span.core.model.commands.AskRequest": "AskRequest",
    "span.core.model.commands.ChallengeConclusionRef": "ChallengeConclusionRef",
    "span.core.model.commands.ChallengeRaise": "ChallengeRaise",
    "span.core.model.commands.ConclusionContentDraft": "ConclusionContentDraft",
    "span.core.model.commands.ConfirmConclusion": "ConfirmConclusion",
    "span.core.model.commands.ContextBoundTarget": "ContextBoundTarget",
    "span.core.model.commands.CorrectConclusion": "CorrectConclusion",
    "span.core.model.commands.CreateChallengeCommand": "CreateChallengeCommand",
    "span.core.model.commands.CreateUnderstandingCommand": "CreateUnderstandingCommand",
    "span.core.model.commands.ExplicitTarget": "ExplicitTarget",
    "span.core.model.commands.GapDraft": "GapDraft",
    "span.core.model.commands.ProposedConclusion": "ProposedConclusion",
    "span.core.model.commands.ReconsiderRequest": "ReconsiderRequest",
    "span.core.model.commands.RecordVerificationCommand": "RecordVerificationCommand",
    "span.core.model.commands.ReplaceConclusion": "ReplaceConclusion",
    "span.core.model.commands.ResolvedChallengeDisposition": "ResolvedChallengeDisposition",
    "span.core.model.commands.StartContextRequest": "StartContextRequest",
    "span.core.model.commands.UnresolvedChallengeDisposition": "UnresolvedChallengeDisposition",
    "span.core.model.commands.UpdateUnderstandingCommand": "UpdateUnderstandingCommand",
    "span.core.model.commands.WithdrawConclusion": "WithdrawConclusion",
    "span.core.model.investigation.AdmittedEvidence": "AdmittedEvidence",
    "span.core.model.investigation.AlreadyAdmittedEvidence": "AlreadyAdmittedEvidence",
    "span.core.model.investigation.DiscoveryObservation": "DiscoveryObservation",
    "span.core.model.investigation.EvidenceAdmissionResult": "EvidenceAdmissionResult",
    "span.core.model.investigation.EvidenceAdmissionView": "EvidenceAdmissionView",
    "span.core.model.investigation.EvidenceDelivery": "EvidenceDelivery",
    "span.core.model.investigation.EvidenceExtendRequest": "EvidenceExtendRequest",
    "span.core.model.investigation.EvidenceRequest": "EvidenceRequest",
    "span.core.model.investigation.EvidenceSourceFailure": "EvidenceSourceFailure",
    "span.core.model.investigation.EvidenceStartRequest": "EvidenceStartRequest",
    "span.core.model.investigation.InvestigationContext": "InvestigationContext",
    "span.core.model.investigation.InvestigationContextRef": "InvestigationContextRef",
    "span.core.model.investigation.LifecycleRetention": "LifecycleRetention",
    "span.core.model.investigation.OmittedEvidence": "OmittedEvidence",
    "span.core.model.investigation.SourceObservation": "SourceObservation",
    "span.core.model.investigation.SourceRange": "SourceRange",
    "span.core.model.outcomes.ChallengeRecorded": "ChallengeRecorded",
    "span.core.model.outcomes.UnderstandingRecorded": "UnderstandingRecorded",
    "span.core.model.outcomes.VerificationRecorded": "VerificationRecorded",
    "span.core.model.primitives.AnswerId": "AnswerId",
    "span.core.model.primitives.AuthorityApplicability": "AuthorityApplicability",
    "span.core.model.primitives.AuthorityBinding": "AuthorityBinding",
    "span.core.model.primitives.AuthoritySupport": "AuthoritySupport",
    "span.core.model.primitives.BoundInfo": "BoundInfo",
    "span.core.model.primitives.CandidateAuthority": "CandidateAuthority",
    "span.core.model.primitives.ChallengeId": "ChallengeId",
    "span.core.model.primitives.ChallengeRevision": "ChallengeRevision",
    "span.core.model.primitives.ClaimId": "ClaimId",
    "span.core.model.primitives.ClaimRef": "ClaimRef",
    "span.core.model.primitives.ConclusionId": "ConclusionId",
    "span.core.model.primitives.ConclusionRevisionNumber": "ConclusionRevisionNumber",
    "span.core.model.primitives.ConclusionRevisionRef": "ConclusionRevisionRef",
    "span.core.model.primitives.DeclaredPrecedence": "DeclaredPrecedence",
    "span.core.model.primitives.DiscoveryObservationId": "DiscoveryObservationId",
    "span.core.model.primitives.EvidenceId": "EvidenceId",
    "span.core.model.primitives.EvidenceIdRef": "EvidenceIdRef",
    "span.core.model.primitives.EvidenceRef": "EvidenceRef",
    "span.core.model.primitives.EvidenceScope": "EvidenceScope",
    "span.core.model.primitives.Freshness": "Freshness",
    "span.core.model.primitives.FreshnessItem": "FreshnessItem",
    "span.core.model.primitives.HandleLifespan": "HandleLifespan",
    "span.core.model.primitives.ImpactItem": "ImpactItem",
    "span.core.model.primitives.InvestigationContextId": "InvestigationContextId",
    "span.core.model.primitives.ProposedChange": "ProposedChange",
    "span.core.model.primitives.QueryBounds": "QueryBounds",
    "span.core.model.primitives.RelationshipId": "RelationshipId",
    "span.core.model.primitives.RelationshipRef": "RelationshipRef",
    "span.core.model.primitives.RequestId": "RequestId",
    "span.core.model.primitives.SemanticBasis": "SemanticBasis",
    "span.core.model.primitives.ServiceBoundsPolicy": "ServiceBoundsPolicy",
    "span.core.model.primitives.SourceObservationId": "SourceObservationId",
    "span.core.model.primitives.Subject": "Subject",
    "span.core.model.primitives.SubjectCandidate": "SubjectCandidate",
    "span.core.model.primitives.SubjectId": "SubjectId",
    "span.core.model.primitives.SubjectResolution": "SubjectResolution",
    "span.core.model.primitives.SubjectSelector": "SubjectSelector",
    "span.core.model.primitives.UnderstandingId": "UnderstandingId",
    "span.core.model.primitives.UnderstandingVersionNumber": "UnderstandingVersionNumber",
    "span.core.model.primitives.VerificationRunId": "VerificationRunId",
    "span.core.model.recording.ContentDigest": "ContentDigest",
    "span.core.model.recording.ReceiptDecision": "ReceiptDecision",
    "span.core.model.recording.RecordingIdentity": "RecordingIdentity",
    "span.core.model.recording.RecordingKey": "RecordingKey",
    "span.core.model.recording.RecordReceipt": "RecordReceipt",
    "span.core.model.recording.RequestBinding": "RequestBinding",
    "span.core.model.repository.EvidenceInventoryItem": "EvidenceInventoryItem",
    "span.core.model.repository.EvidenceInventoryPage": "EvidenceInventoryPage",
    "span.core.model.repository.EvidenceLineRange": "EvidenceLineRange",
    "span.core.model.repository.EvidenceSelection": "EvidenceSelection",
    "span.core.model.repository.EvidenceUnit": "EvidenceUnit",
    "span.core.model.repository.RepositoryIdentity": "RepositoryIdentity",
    "span.core.model.repository.RepositoryState": "RepositoryState",
    "span.core.model.repository.StructuralEdge": "StructuralEdge",
    "span.core.model.repository.StructuralFreshnessReport": "StructuralFreshnessReport",
    "span.core.model.repository.StructuralLocateEntry": "StructuralLocateEntry",
    "span.core.model.repository.StructuralLocateResult": "StructuralLocateResult",
    "span.core.model.repository.StructuralLocation": "StructuralLocation",
    "span.core.model.repository.StructuralNeighborsResult": "StructuralNeighborsResult",
    "span.core.model.repository.StructuralObservation": "StructuralObservation",
    "span.core.model.repository.StructuralOutlineEntry": "StructuralOutlineEntry",
    "span.core.model.repository.StructuralReachNode": "StructuralReachNode",
    "span.core.model.repository.StructuralResult": "StructuralResult",
    "span.core.model.repository.StructuralSearchHit": "StructuralSearchHit",
    "span.core.model.support.AuthoritySupportDependency": "AuthoritySupportDependency",
    "span.core.model.support.ConclusionQualification": "ConclusionQualification",
    "span.core.model.support.ConclusionSupport": "ConclusionSupport",
    "span.core.model.support.DependencyFinding": "DependencyFinding",
    "span.core.model.support.DiscoverySupport": "DiscoverySupport",
    "span.core.model.support.ObservationQualification": "ObservationQualification",
    "span.core.model.support.ObservationSupport": "ObservationSupport",
    "span.core.model.support.PremiseSupport": "PremiseSupport",
    "span.core.model.support.SourceSupport": "SourceSupport",
    "span.core.model.support.SupportEvaluation": "SupportEvaluation",
    "span.core.model.support.SupportQualification": "SupportQualification",
    "span.core.model.support.SupportUnavailable": "SupportUnavailable",
    "span.core.model.support.UnderstandingQualification": "UnderstandingQualification",
    "span.core.model.support.UnderstandingSupport": "UnderstandingSupport",
    "span.core.model.support.VerificationQualification": "VerificationQualification",
    "span.core.model.support.VerificationSupport": "VerificationSupport",
    "span.core.model.support.VerificationSupportRequest": "VerificationSupportRequest",
    "span.core.model.surfaces.StaleConclusionRef": "StaleConclusionRef",
    "span.core.model.surfaces.Surface": "Surface",
    "span.core.model.surfaces.SurfaceBoundary": "SurfaceBoundary",
    "span.core.model.surfaces.SurfaceKey": "SurfaceKey",
    "span.core.model.surfaces.SurfaceReference": "SurfaceReference",
    "span.core.model.surfaces.SurfaceStatus": "SurfaceStatus",
    "span.core.model.surfaces.SurfaceStatusUnavailable": "SurfaceStatusUnavailable",
    "span.core.model.understanding.Challenge": "Challenge",
    "span.core.model.understanding.ChallengeResolution": "ChallengeResolution",
    "span.core.model.understanding.ConclusionRevision": "ConclusionRevision",
    "span.core.model.understanding.ContextRetrievalSelector": "ContextRetrievalSelector",
    "span.core.model.understanding.CurrentUnderstandingSelector": "CurrentUnderstandingSelector",
    "span.core.model.understanding.ReassessRequest": "ReassessRequest",
    "span.core.model.understanding.ReceiptRetrievalSelector": "ReceiptRetrievalSelector",
    "span.core.model.understanding.RecordedQuestionGap": "RecordedQuestionGap",
    "span.core.model.understanding.RecordedQuestionSelector": "RecordedQuestionSelector",
    "span.core.model.understanding.ResolvedChallengeRecord": "ResolvedChallengeRecord",
    "span.core.model.understanding.RetrievedContext": "RetrievedContext",
    "span.core.model.understanding.RetrievedReceipt": "RetrievedReceipt",
    "span.core.model.understanding.RetrievedUnderstanding": "RetrievedUnderstanding",
    "span.core.model.understanding.SupportedConclusion": "SupportedConclusion",
    "span.core.model.understanding.Understanding": "Understanding",
    "span.core.model.understanding.UnderstandingSnapshotSelector": "UnderstandingSnapshotSelector",
    "span.core.model.understanding.UnderstandingVersion": "UnderstandingVersion",
    "span.core.model.understanding.UnresolvedChallengeRecord": "UnresolvedChallengeRecord",
    "span.core.model.understanding.WithdrawnConclusion": "WithdrawnConclusion",
    "span.core.model.verification.ProposedVerificationRun": "ProposedVerificationRun",
    "span.core.model.verification.VerificationRun": "VerificationRun",
    "span.core.model.verification.VerificationScope": "VerificationScope",
    "span.core.schema.record_wire.AddConclusionWire": "AddConclusion",
    "span.core.schema.record_wire.AdmittedDiscoverySupportWire": "AdmittedDiscoverySupport",
    "span.core.schema.record_wire.AdmittedSourceSupportWire": "AdmittedSourceSupport",
    "span.core.schema.record_wire.AuthoritySupportWire": "AuthoritySupport",
    "span.core.schema.record_wire.ConclusionRefWire": "ConclusionRef",
    "span.core.schema.record_wire.ConfirmConclusionWire": "ConfirmConclusion",
    "span.core.schema.record_wire.CorrectConclusionWire": "CorrectConclusion",
    "span.core.schema.record_wire.DiscoveryBoundarySupportWire": "DiscoveryBoundarySupport",
    "span.core.schema.record_wire.DiscoveryScopeWire": "DiscoveryScope",
    "span.core.schema.record_wire.GapWire": "GapInput",
    "span.core.schema.record_wire.IdentityWire": "IdentityInput",
    "span.core.schema.record_wire.PremiseSupportWire": "PremiseSupport",
    "span.core.schema.record_wire.RangeWire": "Range",
    "span.core.schema.record_wire.RecordActionsWire": "RecordActions",
    "span.core.schema.record_wire.RecordRequestWire": "RecordRequest",
    "span.core.schema.record_wire.RecordWireResolver": "RecordWireResolver",
    "span.core.schema.record_wire.ReplaceActionWire": "ReplaceConclusion",
    "span.core.schema.record_wire.ResolvedDispositionWire": "ResolvedDisposition",
    "span.core.schema.record_wire.SourceSupportWire": "SourceSupport",
    "span.core.schema.record_wire.SurfaceBoundaryWire": "SurfaceBoundaryInput",
    "span.core.schema.record_wire.SurfaceKeyWire": "SurfaceKeyInput",
    "span.core.schema.record_wire.SurfaceWire": "SurfaceInput",
    "span.core.schema.record_wire.UnresolvedDispositionWire": "UnresolvedDisposition",
    "span.core.schema.record_wire.VerificationRunWire": "VerificationRunInput",
    "span.core.schema.record_wire.WithdrawActionWire": "WithdrawConclusion",
    "span.shell.mcp.models.ServiceContext": "ServiceContext",
    "span.shell.mcp.models.ToolError": "ToolError",
    "span.shell.mcp.models.ToolResult": "ToolResult",
}


def _type_key(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def public_type_tag(cls: type) -> str:
    key = _type_key(cls)
    try:
        return _PUBLIC_TYPE_TAGS[key]
    except KeyError:
        raise TypeError(
            "public union member has no declared protocol discriminator"
        ) from None


def public_schema_name(cls: type) -> str:
    key = _type_key(cls)
    try:
        return _PUBLIC_SCHEMA_NAMES[key]
    except KeyError:
        raise TypeError("schema carrier has no declared public protocol name") from None


def from_wire(root: object, payload: dict) -> object:
    """Strict ingress for the compact agent-facing grammar (J-8/S6.2)."""
    from span.core import model as _m

    if not isinstance(payload, dict):
        raise ValueError("request payload must be an object")
    if "$type" in payload:
        raise ValueError("top-level $type is never supplied on the wire")
    tagged = _inject(root, payload, "")
    return _m.from_canonical(_typing.cast(type, root), tagged)


def _inject(hint: object, value: object, path: str) -> object:
    if value is None:
        return None
    origin = _typing.get_origin(hint)
    args = _typing.get_args(hint)
    if origin is _typing.Union or origin is _types.UnionType:
        dms = [a for a in args if isinstance(a, type) and _dataclasses.is_dataclass(a)]
        non_none = [a for a in args if a is not type(None)]
        if len(dms) >= 2:
            if not isinstance(value, dict) or not isinstance(value.get("$type"), str):
                accepted = ", ".join(public_type_tag(member) for member in dms)
                raise ValueError(
                    f"missing $type discriminator at {path or 'root'} "
                    f"(accepted: {accepted})"
                )
            tag = value["$type"]
            member = next((mm for mm in dms if public_type_tag(mm) == tag), None)
            if member is None:
                raise ValueError(f"unknown $type {tag!r} at {path or 'root'}")
            return _inject_dataclass(member, value, path, keep_tag=True)
        if len(dms) == 1 and len(non_none) == 1:
            return _inject_dataclass(dms[0], value, path, keep_tag=False)
        return value
    if isinstance(hint, type) and _dataclasses.is_dataclass(hint):
        return _inject_dataclass(hint, value, path, keep_tag=False)
    if origin in (tuple, list):
        if not isinstance(value, list):
            raise ValueError(f"expected list at {path or 'root'}, got {value!r}")
        item = args[0] if args else None
        # Aggregate sibling faults so one call reports every bad member
        # instead of the caller discovering them one round trip at a
        # time; a single fault keeps its exact previous text.
        injected: list[object] = []
        faults: list[str] = []
        for i, v in enumerate(value):
            try:
                injected.append(_inject(item, v, f"{path}[{i}]"))
            except ValueError as exc:
                faults.append(str(exc))
                injected.append(v)
        if faults:
            raise ValueError("; ".join(faults))
        return injected
    return value


def _inject_dataclass(cls: type, value: object, path: str, *, keep_tag: bool) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"expected object at {path or cls.__name__}")
    hints = _typing.get_type_hints(cls)
    fields = {field.name: field for field in _dataclasses.fields(cls)}
    at = f"{path}: " if path else ""
    faults: list[str] = []
    if "$type" in value and not keep_tag and value["$type"] != public_type_tag(cls):
        # A redundant tag that names the only candidate carrier is accepted:
        # it carries no ambiguity. A tag naming anything else is a mistake.
        faults.append(
            "unexpected $type at unambiguous position: "
            f"{path or public_schema_name(cls)}; this position accepts "
            f"{public_schema_name(cls)} without a $type"
        )
    # The tagging pass is the first ingress pass, so it also reports the
    # field-shape faults the strict decoder would raise later; otherwise
    # a tag fault and an unknown/missing field cost two round trips.
    # Texts match the decoder's for the single-fault case.
    unknown = sorted(key for key in value if key != "$type" and key not in fields)
    if unknown:
        faults.append(f"{at}unknown fields for {cls.__name__}: {unknown}")
    for field in fields.values():
        if field.name in value:
            continue
        if (
            field.default is _dataclasses.MISSING
            and field.default_factory is _dataclasses.MISSING  # type: ignore[misc]
        ):
            faults.append(f"{at}missing field {field.name!r} for {cls.__name__}")
    out: dict = {"$type": cls.__name__}
    for key, v in value.items():
        if key == "$type" or key not in fields:
            continue
        child_path = f"{path}.{key}" if path else key
        try:
            out[key] = _inject(hints.get(key), v, child_path)
        except ValueError as exc:
            faults.append(str(exc))
            out[key] = v
    if faults:
        raise ValueError("; ".join(faults))
    return out


def to_wire(value: object, hint: object) -> object:
    """Project a canonical object to the compact grammar (S6.4)."""
    if value is None:
        return None
    origin = _typing.get_origin(hint)
    args = _typing.get_args(hint)
    if origin is _typing.Union or origin is _types.UnionType:
        dms = [a for a in args if isinstance(a, type) and _dataclasses.is_dataclass(a)]
        if len(dms) >= 2:
            tag = value.get("$type") if isinstance(value, dict) else None
            member = next((mm for mm in dms if mm.__name__ == tag), None)
            if member is None:
                return value
            return _compact_dataclass(member, value, keep_tag=True)
        if len(dms) == 1:
            return _compact_dataclass(dms[0], value, keep_tag=False)
        return value
    if isinstance(hint, type) and _dataclasses.is_dataclass(hint):
        return _compact_dataclass(hint, value, keep_tag=False)
    if origin in (tuple, list):
        if not isinstance(value, list):
            raise TypeError(f"expected canonical list, got {value!r}")
        item = args[0] if args else None
        return [to_wire(v, item) for v in value]
    return value


def to_wire_root(cls: type, canonical: object) -> object:
    """Egress root: retain the root result ``$type`` (S6.4)."""
    return _compact_dataclass(cls, canonical, keep_tag=True)


def _compact_dataclass(cls: type, value: object, *, keep_tag: bool) -> object:
    if not isinstance(value, dict):
        return value
    hints = _typing.get_type_hints(cls)
    out: dict = {}
    for key, v in value.items():
        if key == "$type":
            if keep_tag:
                out[key] = public_type_tag(cls)
            continue
        out[key] = to_wire(v, hints.get(key))
    return out


def compact_payload(root: type, payload: dict) -> dict:
    """Compact a fully-tagged transport payload to the agent-facing grammar.

    Wire projection mirroring ``from_wire``: a single-dataclass
    field drops ``$type``; a genuine dataclass union keeps it. Unknown
    transport-only keys pass through unchanged.
    """
    compacted = _compact_dataclass(root, payload, keep_tag=False)
    return compacted if isinstance(compacted, dict) else payload

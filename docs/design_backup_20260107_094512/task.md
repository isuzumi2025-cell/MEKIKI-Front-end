# Enhanced Comparison Matrix with Dynamic Clustering

## Overview
Transform the embedded comparison matrix frame into an advanced proofing workspace with:
- AI-based page break detection
- Dynamic clustering OCR (Google Vision API)  
- Editable paragraph regions with sync numbering
- Real-time text synchronization

## Tasks

### Phase 1: Core Engine Enhancement
- [ ] Enhance `CloudOCREngine` with page break detection
- [ ] Add sync number generation for matched paragraphs
- [ ] Create `PageBreakDetector` class for AI-based splitting

### Phase 2: New UI Component - AdvancedComparisonView
- [ ] Create `advanced_comparison_view.py` with dual-pane layout
- [ ] Implement overview map with page thumbnails
- [ ] Implement page detail view with editable regions
- [ ] Add area code overlay renderer

### Phase 3: Interactive Region Editing
- [ ] Implement drag-to-resize region handles
- [ ] Add region split/merge functionality
- [ ] Enable real-time text recalculation on edit
- [ ] Add sync number update on region change

### Phase 4: Sync Matching Engine
- [ ] Create paragraph similarity matcher
- [ ] Generate sync numbers for matched pairs
- [ ] Implement visual sync highlighting

### Phase 5: Integration & Testing
- [ ] Replace embedded frame content
- [ ] Connect to existing comparison_queue data
- [ ] Test with real Web/PDF data

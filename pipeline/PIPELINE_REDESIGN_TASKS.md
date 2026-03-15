# Pipeline Redesign Task List

> Smart Learning App - NIOS Study Assistant Pipeline Redesign
> Created: March 16, 2026

## Project Context

**Objective**: Redesign pipeline stages 03-06 to handle Marker PDF extraction output and optimize for smart learning app capabilities with granular progress tracking.

**Current Status**:

- ✅ Stage 01-02: Working (Chapter URLs + Marker extraction on Kaggle)
- ❌ Stage 03: DELETED (structure_content.py removed)
- ⚠️ Stage 04-06: Incompatible with Marker JSON format
- 📊 **Data Available**: 7 class 10 subjects extracted via Marker

---

## Phase 1: Stage 03 - Smart Content Extraction

### 1.1 Marker JSON Analysis & Parser

- [ ] Create comprehensive analysis of Marker JSON structure from existing extractions
- [ ] Document all block types: Text, Picture, SectionHeader, Figure, Table, List, etc.
- [ ] Map block type hierarchy and relationships (parent-child structure)
- [ ] Identify image extraction patterns (base64 data, polygon coordinates)
- [ ] Create utility functions for parsing nested children arrays
- [ ] Handle polygon coordinate data for precise content positioning

### 1.2 Content Block Identification System

- [ ] Design auto-detection logic for educational content types:
  - [ ] Concepts and definitions (often after section headers)
  - [ ] Mathematical formulas (LaTeX patterns, equation blocks)
  - [ ] Examples and illustrations (numbered/bulleted content)
  - [ ] Diagrams and figures (Picture blocks with captions)
  - [ ] Common mistakes sections (pattern recognition)
- [ ] Create content classification algorithm based on text patterns
- [ ] Implement learning objective detection from section structure

### 1.3 Topic Granularity Engine

- [ ] Design smart topic segmentation algorithm:
  - [ ] Use SectionHeader blocks as primary topic boundaries
  - [ ] Implement content length analysis for topic splitting
  - [ ] Create meaningful topic title generation (not "Part 1", "Section A")
  - [ ] Calculate optimal granularity for progress tracking (target: 5-10 min topics)
- [ ] Implement goal_tier assignment logic (CORE/STANDARD/ADVANCED)
- [ ] Generate prerequisite topic chains based on content dependencies

### 1.4 Learning-Optimized Content Generation

- [ ] Create structure_content.py replacement with Marker JSON support
- [ ] Implement hybrid API strategy (DeepSeek for text + local processing for images)
- [ ] Design prompt engineering for educational content extraction:
  - [ ] Summary bullet generation (2-4 concise points)
  - [ ] Why_important explanations for exam context
  - [ ] Common mistakes identification and categorization
- [ ] Implement exact_source_quote extraction for verification
- [ ] Add cost optimization with smart batching and retries

### 1.5 Image and Media Processing

- [ ] Create image extraction pipeline from base64 data in Marker JSON
- [ ] Implement image filtering (remove headers/footers, keep educational content)
- [ ] Design image optimization and conversion (PNG/JPEG optimization)
- [ ] Create media_url generation for future Cloudflare R2 integration
- [ ] Add image captioning and context association with content blocks

---

## Phase 2: Stage 04-06 Smart Learning Adaptations

### 2.1 Stage 04 - Learning-Focused Verification

- [ ] Update verify_content.py to work with new Stage 03 output format
- [ ] Implement educational quality checks:
  - [ ] Topic learning objective clarity verification
  - [ ] Prerequisite chain logical validation
  - [ ] Content completeness assessment per topic
  - [ ] Goal_tier assignment validation
- [ ] Enhance exact_source_quote verification for Marker JSON format
- [ ] Add verification stats for learning app quality metrics

### 2.2 Stage 05 - Enhanced PYQ Processing

- [ ] Update solve_pyqs.py for smarter topic mapping:
  - [ ] Implement auto-mapping of PYQ questions to granular topics
  - [ ] Create difficulty progression analysis
  - [ ] Generate practice sets aligned with learning objectives
  - [ ] Add frequency_score calculation based on historical patterns
- [ ] Enhance Claude-powered solution generation:
  - [ ] Step-by-step breakdown optimized for learning
  - [ ] Common error patterns and prevention
  - [ ] Hint generation for guided problem solving

### 2.3 Stage 06 - Smart Backend Seeding

- [ ] Update seed_backend.py for learning app requirements:
  - [ ] Generate progress tracking metadata per topic
  - [ ] Create learning path algorithms data
  - [ ] Add spaced repetition scheduling data
  - [ ] Generate performance analytics baseline data
- [ ] Optimize TypeScript generation for app performance
- [ ] Add data validation for frontend consumption

---

## Phase 3: Testing & Quality Assurance

### 3.1 Single Subject Pipeline Testing

- [ ] Choose test subject (recommend: maths-10 for faster processing)
- [ ] Run complete pipeline stages 03-06 on test subject
- [ ] Validate output quality against learning app requirements
- [ ] Performance testing: API costs, processing time, error rates
- [ ] Manual content review: educational accuracy and completeness

### 3.2 Content Quality Validation

- [ ] Create educational content review checklist
- [ ] Test topic granularity for progress tracking usability
- [ ] Validate learning objective clarity and achievement
- [ ] Check prerequisite chain logical flow
- [ ] Verify that goal_tier assignments support learning paths

### 3.3 Integration Testing

- [ ] Test backend integration with new generated data structure
- [ ] Validate frontend consumption of redesigned data format
- [ ] Check API performance with updated content structure
- [ ] Test progress tracking functionality with granular topics

---

## Phase 4: Production Scale & Optimization

### 4.1 Multi-Subject Processing

- [ ] Process all class 10 subjects (7 available) through redesigned pipeline
- [ ] Complete class 12 subjects extraction and processing
- [ ] Implement batch processing optimization for cost efficiency
- [ ] Add progress monitoring and checkpoint recovery for large-scale runs

### 4.2 Performance & Cost Optimization

- [ ] Implement smart API usage patterns:
  - [ ] Request batching and rate limiting
  - [ ] Cost monitoring and budget controls
  - [ ] Error handling and retry logic
  - [ ] Content caching strategies
- [ ] Optimize processing pipeline for memory efficiency
- [ ] Add monitoring and logging for production usage

### 4.3 Documentation & Maintenance

- [ ] Update MASTER_PLAN.md with new pipeline architecture
- [ ] Create comprehensive README for Stage 03-06 operations
- [ ] Document API usage patterns and cost calculations
- [ ] Create maintenance procedures for content updates
- [ ] Add troubleshooting guides for common issues

---

## Phase 5: Smart Learning App Integration

### 5.1 Advanced Learning Features

- [ ] Implement adaptive learning path generation based on topic granularity
- [ ] Create personalized content recommendation engine
- [ ] Add difficulty progression algorithms
- [ ] Implement spaced repetition scheduling with granular topics

### 5.2 Analytics & Insights

- [ ] Create learning analytics data pipeline
- [ ] Implement performance tracking across granular topics
- [ ] Add content effectiveness measurement systems
- [ ] Generate insights for content optimization

---

## Success Criteria

- [ ] **Stage 03**: Successfully convert Marker JSON to structured learning content for all subjects
- [ ] **Content Quality**: 85%+ verification pass rate with educational review approval
- [ ] **Cost Efficiency**: Processing costs under $50 per subject for full pipeline
- [ ] **Learning App Ready**: Granular topics enable meaningful progress tracking
- [ ] **Performance**: Complete pipeline processes one subject in under 2 hours
- [ ] **Integration**: Backend generates TypeScript data compatible with frontend expectations

---

## Notes & Considerations

**API Strategy**: Primary focus on DeepSeek API for cost efficiency with Claude fallback for complex reasoning
**Quality vs Cost**: Hybrid approach balancing educational quality with processing costs
**Topic Granularity**: Target 5-10 minute learning chunks for optimal progress tracking
**Image Handling**: Local processing preferred for cost optimization
**Verification**: Maintain exact_source_quote requirement for anti-hallucination

---

_Last Updated: March 16, 2026_
_Next Review: After Phase 1 completion_

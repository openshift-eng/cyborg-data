// Package testing provides internal test utilities for orgdatacore.
package testing

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"sync"
	"time"
)

// FakeBlob represents a fake GCS blob for testing.
type FakeBlob struct {
	Name       string
	Content    []byte
	Generation int64
	Updated    time.Time
}

// FakeBucket represents a fake GCS bucket for testing. It retains every
// generation of each blob in history to emulate object versioning.
type FakeBucket struct {
	Name    string
	blobs   map[string]*FakeBlob   // name -> current (live) generation
	history map[string][]*FakeBlob // name -> all generations, oldest first
	mu      sync.RWMutex
}

// NewFakeBucket creates a new fake bucket.
func NewFakeBucket(name string) *FakeBucket {
	return &FakeBucket{
		Name:    name,
		blobs:   make(map[string]*FakeBlob),
		history: make(map[string][]*FakeBlob),
	}
}

// AddBlob adds a blob with content to the bucket (generation 1).
func (b *FakeBucket) AddBlob(name string, content []byte) *FakeBlob {
	return b.AddBlobAt(name, content, time.Now())
}

// AddBlobAt adds a blob with content and an explicit creation time. Used to
// build deterministic version histories in tests.
func (b *FakeBucket) AddBlobAt(name string, content []byte, created time.Time) *FakeBlob {
	b.mu.Lock()
	defer b.mu.Unlock()

	blob := &FakeBlob{
		Name:       name,
		Content:    content,
		Generation: 1,
		Updated:    created,
	}
	b.blobs[name] = blob
	b.history[name] = []*FakeBlob{blob}
	return blob
}

// GetBlob retrieves the current (live) blob from the bucket.
func (b *FakeBucket) GetBlob(name string) (*FakeBlob, bool) {
	b.mu.RLock()
	defer b.mu.RUnlock()
	blob, ok := b.blobs[name]
	return blob, ok
}

// UpdateBlob writes a new generation of an existing blob, retaining prior ones.
func (b *FakeBucket) UpdateBlob(name string, content []byte) error {
	return b.UpdateBlobAt(name, content, time.Now())
}

// UpdateBlobAt writes a new generation with an explicit creation time.
func (b *FakeBucket) UpdateBlobAt(name string, content []byte, created time.Time) error {
	b.mu.Lock()
	defer b.mu.Unlock()

	prev, ok := b.blobs[name]
	if !ok {
		return fmt.Errorf("blob %s not found", name)
	}
	next := &FakeBlob{
		Name:       name,
		Content:    content,
		Generation: prev.Generation + 1,
		Updated:    created,
	}
	b.blobs[name] = next
	b.history[name] = append(b.history[name], next)
	return nil
}

// Versions returns a copy of all retained generations of a blob, oldest first.
func (b *FakeBucket) Versions(name string) []*FakeBlob {
	b.mu.RLock()
	defer b.mu.RUnlock()
	versions := b.history[name]
	out := make([]*FakeBlob, len(versions))
	copy(out, versions)
	return out
}

// GetGenerationBlob returns a specific retained generation of a blob.
func (b *FakeBucket) GetGenerationBlob(name string, generation int64) (*FakeBlob, bool) {
	b.mu.RLock()
	defer b.mu.RUnlock()
	for _, blob := range b.history[name] {
		if blob.Generation == generation {
			return blob, true
		}
	}
	return nil, false
}

// FakeGCSClient represents a fake GCS client for testing.
type FakeGCSClient struct {
	buckets map[string]*FakeBucket
	mu      sync.RWMutex
}

// NewFakeGCSClient creates a new fake GCS client.
func NewFakeGCSClient() *FakeGCSClient {
	return &FakeGCSClient{
		buckets: make(map[string]*FakeBucket),
	}
}

// AddBucket adds a bucket to the client.
func (c *FakeGCSClient) AddBucket(name string) *FakeBucket {
	c.mu.Lock()
	defer c.mu.Unlock()

	bucket := NewFakeBucket(name)
	c.buckets[name] = bucket
	return bucket
}

// GetBucket retrieves a bucket from the client.
func (c *FakeGCSClient) GetBucket(name string) (*FakeBucket, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	bucket, ok := c.buckets[name]
	return bucket, ok
}

// FakeGCSDataSource is a DataSource implementation using fake GCS for testing.
type FakeGCSDataSource struct {
	bucket     *FakeBucket
	objectPath string
	bucketName string
}

// NewFakeGCSDataSource creates a new fake GCS data source.
func NewFakeGCSDataSource(bucketName, objectPath string, content []byte) *FakeGCSDataSource {
	return NewFakeGCSDataSourceAt(bucketName, objectPath, content, time.Now())
}

// NewFakeGCSDataSourceAt creates a fake GCS data source whose first generation
// has an explicit creation time, for building deterministic version histories.
func NewFakeGCSDataSourceAt(bucketName, objectPath string, content []byte, created time.Time) *FakeGCSDataSource {
	bucket := NewFakeBucket(bucketName)
	bucket.AddBlobAt(objectPath, content, created)

	return &FakeGCSDataSource{
		bucket:     bucket,
		objectPath: objectPath,
		bucketName: bucketName,
	}
}

// Load returns a reader for the blob content.
func (f *FakeGCSDataSource) Load(ctx context.Context) (io.ReadCloser, error) {
	blob, ok := f.bucket.GetBlob(f.objectPath)
	if !ok {
		return nil, fmt.Errorf("blob %s not found in bucket %s", f.objectPath, f.bucketName)
	}
	return io.NopCloser(bytes.NewReader(blob.Content)), nil
}

// Watch monitors for changes (simplified for testing - just calls callback once).
func (f *FakeGCSDataSource) Watch(ctx context.Context, callback func() error) error {
	// In a real implementation, this would poll for changes
	// For testing, we just return immediately without starting a watcher
	return nil
}

// String returns a description of this data source.
func (f *FakeGCSDataSource) String() string {
	return fmt.Sprintf("gs://%s/%s (fake)", f.bucketName, f.objectPath)
}

// Close cleans up resources (no-op for fake).
func (f *FakeGCSDataSource) Close() error {
	return nil
}

// UpdateContent updates the blob content for testing hot reload.
func (f *FakeGCSDataSource) UpdateContent(content []byte) error {
	return f.bucket.UpdateBlob(f.objectPath, content)
}

// AddVersionAt appends a new generation with an explicit creation time, for
// building deterministic version histories in time-travel tests.
func (f *FakeGCSDataSource) AddVersionAt(content []byte, created time.Time) error {
	return f.bucket.UpdateBlobAt(f.objectPath, content, created)
}

// Bucket returns the underlying fake bucket, exposing version history to tests
// that build a HistoricalDataSource adapter over this source. (The orgdatacore
// DataVersionRef type cannot be referenced here without an import cycle, so the
// adapter lives in the orgdatacore test package.)
func (f *FakeGCSDataSource) Bucket() *FakeBucket { return f.bucket }

// ObjectPath returns the configured object path.
func (f *FakeGCSDataSource) ObjectPath() string { return f.objectPath }

// GetGeneration returns the current generation of the blob.
func (f *FakeGCSDataSource) GetGeneration() (int64, error) {
	blob, ok := f.bucket.GetBlob(f.objectPath)
	if !ok {
		return 0, fmt.Errorf("blob not found")
	}
	return blob.Generation, nil
}

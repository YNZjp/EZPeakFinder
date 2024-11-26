import numpy as np
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d


class AnalyzeComments:

    def __init__(self, comments, video_length, time_bin=30):
        self.comments = comments
        self.video_length = video_length
        self.time_bin = time_bin
        self.bins = np.arange(0, video_length + time_bin, time_bin)

    def _aggregate_features(self, sensitivity):
        counts = np.zeros(len(self.bins) - 1)
        diversity = np.zeros(len(self.bins) - 1)

        for comment in self.comments:
            time = comment["content_offset_seconds"]
            message = comment["message"]
            index = np.digitize(time, self.bins) - 1

            if 0 <= index < len(counts):
                counts[index] += 1
                diversity[index] += len(set(message))

        burstiness = np.diff(counts, prepend=0)
        window_size = int(10 / sensitivity)
        counts = self._local_normalize(counts, window_size)
        diversity = self._local_normalize(diversity, window_size)
        burstiness = self._local_normalize(np.abs(burstiness), window_size)

        return counts, diversity, burstiness

    def _local_normalize(self, data, window_size):
        normalized = np.zeros_like(data)
        for i in range(len(data)):
            start = max(0, i - window_size)
            end = min(len(data), i + window_size)
            local_max = np.max(data[start:end]) + 1e-10
            normalized[i] = data[i] / local_max
        return normalized

    def _dynamic_threshold(self, smoothed_scores, window_size):
        dynamic_thresholds = np.zeros_like(smoothed_scores)
        for i in range(len(smoothed_scores)):
            start = max(0, i - window_size)
            end = min(len(smoothed_scores), i + window_size)
            local_mean = np.mean(smoothed_scores[start:end])
            local_std = np.std(smoothed_scores[start:end])
            dynamic_thresholds[i] = local_mean + local_std * 0.5
        return dynamic_thresholds

    def detect_peaks(self, sensitivity=5):
        sensitivity = max(1, min(sensitivity, 10)) / 10.0
        counts, diversity, burstiness = self._aggregate_features(sensitivity)
        base_score = (counts * (0.5 + sensitivity * 0.2) + diversity *
                      (0.3 - sensitivity * 0.1) + burstiness * 0.2)
        smoothed_scores = gaussian_filter1d(base_score, sigma=2)
        window_size = int(10 / sensitivity)
        dynamic_thresholds = self._dynamic_threshold(smoothed_scores,
                                                     window_size)
        peaks, _ = find_peaks(smoothed_scores, height=dynamic_thresholds)
        return self.bins[:-1], smoothed_scores, peaks
